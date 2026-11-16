'use strict';

const el = id => document.getElementById(id);
let task = null;
let mode = 'letter';
let alphabet = {};
let phase = 'loading';
let stream = null;
let recorder = null;
let timer = null;
let clock = null;
let previewURL = null;
let pendingJob = null;
let pollTimer = null;
let rawTranscript = '';
let cancelling = false;
let game = {active: false, graded: false, pending: null};
let lastTick = performance.now();

async function request(path, body) {
    const response = await fetch(path, body === undefined ? {} : {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw Error(data.error || 'Anfrage fehlgeschlagen.');
    return data;
}

function setPhase(value, status) {
    phase = value;
    document.body.dataset.phase = value;
    el('gameProcessing').hidden = !(game.active && ['uploading', 'transcribing', 'checking'].includes(value));
    el('playAgain').disabled = !['ready', 'review'].includes(value);
    const locked = !['ready', 'review'].includes(value);
    el('record').disabled = locked || !task || game.active;
    el('record').setAttribute('aria-pressed', String(value === 'recording'));
    el('recordStop').disabled = value !== 'recording';
    el('next').disabled = locked || !task || game.active;
    el('reveal').disabled = locked || !task || game.active;
    el('manualCheck').disabled = locked || !task || game.active;
    el('checkText').disabled = locked || !task;
    el('microphone').disabled = locked;
    el('language').disabled = locked;
    document.querySelectorAll('[data-mode]').forEach(button => { button.disabled = locked || game.active; });
    el('gameStart').disabled = locked || game.active;
    el('gameEnd').disabled = locked;
    el('gameConfirm').hidden = true;
    el('speed').disabled = locked || game.active;
    el('gameEnd').disabled = !game.active || !['recording'].includes(value);
    el('recordStop').disabled = value !== 'recording' || game.active;
    el('confirmRound').disabled = locked || !game.pending || game.graded;
    el('correction').hidden = game.active;
    document.querySelector('.manual').hidden = game.active;
    if (game.active) el('next').textContent = 'Nächste Runde →';
    if (status) el('recordStatus').textContent = status;
}

function fail(error) {
    if (game.active) {
        game.active = false;
        clearInterval(clock);
        clearTimeout(timer);
        renderGame();
    }
    el('gameProcessing').hidden = true;
    el('error').textContent = error.message;
    setPhase('ready', 'Keine Wertung. Bitte erneut versuchen.');
}

async function nextTask() {
    if (game.active) return;
    setPhase('loading', 'Neue Aufgabe …');
    el('error').textContent = '';
    try {
        task = await request('/api/trainer/task', {mode});
        el('prompt').textContent = task.prompt;
        el('next').textContent = game.active ? 'Nächste Runde →' : 'Nächste Aufgabe →';
        document.querySelectorAll('[data-mode]').forEach(button => {
            button.setAttribute('aria-pressed', String(button.dataset.mode === mode));
        });
        el('answer').hidden = true;
        el('solution').hidden = true;
        el('correction').open = false;
        el('manualText').value = '';
        el('transcript').value = '';
        rawTranscript = '';
        clearPreview();
        lastTick = performance.now();
        setPhase('ready', 'Bereit. Sprich die Codewörter in der angezeigten Reihenfolge.');
    } catch (error) {
        task = null;
        if (game.active) finishGame('Verbindung unterbrochen');
        fail(error);
        el('next').disabled = false;
        el('next').textContent = 'Verbindung erneut versuchen →';
    }
}

function clearPreview() {
    el('preview').pause();
    el('preview').removeAttribute('src');
    el('preview').hidden = true;
    if (previewURL) URL.revokeObjectURL(previewURL);
    previewURL = null;
}

async function checkAnswer(text, source) {
    setPhase('checking', 'Antwort wird verglichen …');
    el('error').textContent = '';
    try {
        const result = await request('/api/trainer/check', {task_id: task.id, text});
        el('answer').hidden = false;
        el('answerSource').textContent = source;
        if (source !== 'MANUELL KORRIGIERT') rawTranscript = text;
        el('rawText').textContent = source === 'MANUELL KORRIGIERT'
            ? 'Originalantwort: ' + rawTranscript + '\nKorrigiert: ' + text : text;
        el('transcript').value = text;
        el('verdict').textContent = result.passed ? 'Check! Alles richtig.'
            : `${result.correct} von ${result.total} Codewörtern richtig · ${result.score} %`;
        el('verdict').dataset.passed = String(result.passed);
        const labels = {correct: 'Richtig', wrong: 'Abweichung', missing: 'Fehlt', extra: 'Zusätzlich'};
        el('feedback').replaceChildren(...result.feedback.map(item => {
            const row = document.createElement('tr');
            row.dataset.state = item.state;
            [item.letter || '—', item.expected || '—', item.heard || '—', labels[item.state]].forEach(value => {
                const cell = document.createElement('td');
                cell.textContent = value;
                row.append(cell);
            });
            return row;
        }));
        el('expected').textContent = 'Lösung: ' + result.expected.join(' · ');
        if (game.active) finishGame(result);
        setPhase('review', 'Prüfung abgeschlossen. Wiederholen oder nächste Aufgabe wählen.');
    } catch (error) { fail(error); }
}

function releaseStream() {
    clearTimeout(timer);
    clearInterval(clock);
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
}

async function releaseRecording() {
    releaseStream();
}

function stopRecording() {
    if (recorder && recorder.state === 'recording') {
        setPhase('uploading', 'Aufnahme wird vorbereitet …');
        clearTimeout(timer);
        clearInterval(clock);
        recorder.stop();
    }
}

async function pollTranscription() {
    if (!pendingJob) return;
    try {
        const t = await request('/api/transcriptions/' + pendingJob);
        if (t.id !== pendingJob) throw Error('Die Aufnahme wurde durch einen anderen Vorgang ersetzt. Bitte erneut aufnehmen.');
        if (t.state === 'done') {
            pendingJob = null;
            rawTranscript = t.text;
            await checkAnswer(t.text, 'SPRACHERKENNUNG');
            return;
        }
        if (t.state === 'error') throw Error('Sprache nicht sicher erkannt. ' + t.error);
        pollTimer = setTimeout(pollTranscription, 800);
    } catch (error) {
        pendingJob = null;
        fail(error);
    }
}

async function startRecording() {
    if (game.active) game.pending = null;
    el('error').textContent = '';
    setPhase('permission', 'Mikrofon wird aktiviert …');
    el('answer').hidden = true;
    clearPreview();
    cancelling = false;
    try {
        if (!navigator.mediaDevices || !window.MediaRecorder) {
            throw Error('Mikrofonaufnahme benötigt Chromium und eine lokale Adresse oder HTTPS.');
        }
        const mime = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4']
            .find(value => MediaRecorder.isTypeSupported(value));
        if (!mime) throw Error('Kein unterstütztes Aufnahmeformat verfügbar.');
        const device = el('microphone').value;
        stream = await navigator.mediaDevices.getUserMedia({audio: {
            ...(device ? {deviceId: {exact: device}} : {}),
            echoCancellation: true, noiseSuppression: true,
        }});
        const devices = await navigator.mediaDevices.enumerateDevices();
        el('microphone').replaceChildren(new Option('Standardmikrofon', ''),
            ...devices.filter(d => d.kind === 'audioinput' && d.deviceId !== 'default')
                .map(d => new Option(d.label || 'Mikrofon', d.deviceId)));
        el('microphone').value = device;
        const chunks = [];
        const language = el('language').value;
        recorder = new MediaRecorder(stream, {mimeType: mime});
        recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
        recorder.onerror = async event => {
            cancelling = true;
            try { await releaseRecording(); } catch (_) { /* Release local tracks even if disconnected. */ }
            fail(event.error || Error('Aufnahme fehlgeschlagen.'));
        };
        recorder.onstop = async () => {
            if (cancelling) return;
            try {
                await releaseRecording();
                const blob = new Blob(chunks, {type: mime});
                if (!blob.size) throw Error('Die Aufnahme ist leer.');
                previewURL = URL.createObjectURL(blob);
                el('preview').src = previewURL;
                el('preview').hidden = false;
                const response = await fetch('/api/transcribe?language=' + language, {
                    method: 'POST', headers: {'Content-Type': mime}, body: blob,
                });
                const result = await response.json();
                if (!response.ok) throw Error(result.error || 'Aufnahme konnte nicht verarbeitet werden.');
                pendingJob = result.id;
                setPhase('transcribing', 'Auswertung läuft … Deine Aufnahme wird erkannt und anschließend verglichen.');
                pollTranscription();
            } catch (error) { fail(error); }
        };
        recorder.start(1000);
        if (game.active) {
            runChallenge();
            return;
        }
        setPhase('recording', 'Aufnahme läuft · 0 / 60 Sekunden');
        const started = Date.now();
        clock = setInterval(() => {
            el('recordStatus').textContent = 'Aufnahme läuft · ' + Math.floor((Date.now() - started) / 1000) + ' / 60 Sekunden';
        }, 250);
        timer = setTimeout(stopRecording, 60000);
    } catch (error) {
        try { await releaseRecording(); } catch (_) { /* Preserve the original microphone error. */ }
        if (error.name === 'NotAllowedError') error = Error('Mikrofonzugriff nicht erlaubt. Bitte im Browser freigeben oder per Texteingabe üben.');
        fail(error);
    }
}

document.querySelectorAll('[data-mode]').forEach(button => {
    button.onclick = () => { mode = button.dataset.mode; nextTask(); };
});
el('next').onclick = nextTask;
el('reveal').onclick = () => {
    el('solution').textContent = [...task.prompt].map(letter => alphabet[letter]).join(' · ');
    el('solution').hidden = !el('solution').hidden;
};
el('record').onclick = startRecording;
el('recordStop').onclick = stopRecording;
el('manualCheck').onclick = () => checkAnswer(el('manualText').value, 'TEXTEINGABE');
el('checkText').onclick = () => checkAnswer(el('transcript').value, 'MANUELL KORRIGIERT');

function renderGame() {
    document.body.classList.toggle('playing', game.active);
    el('gameBoard').hidden = !game.active;
    document.querySelector('.modes').hidden = game.active;
    document.querySelector('.task-actions').hidden = game.active;
    document.querySelector('.record-actions').hidden = game.active;
    if (!game.active) return;
    el('gameRound').textContent = game.round + ' / 10';
    el('gameTime').textContent = (game.interval / 1000) + ' s / Buchstabe';
}

async function startGame() {
    if (game.active || !['ready', 'review'].includes(phase)) return;
    game = {active: true, round: 0, interval: Number(el('speed').value)};
    el('gameSummary').hidden = true;
    el('solution').hidden = true;
    el('alphabetPanel').hidden = true;
    el('alphabetToggle').setAttribute('aria-expanded', 'false');
    el('alphabetToggle').textContent = 'NATO-Alphabet einblenden';
    renderGame();
    setPhase('loading', 'Zehn Buchstaben werden vorbereitet …');
    try {
        task = await request('/api/trainer/task', {mode: 'challenge'});
        await startRecording();
    } catch (error) { fail(error); }
}

function runChallenge() {
    const started = performance.now();
    const countdown = 4000;
    el('gameClock').max = game.interval;
    setPhase('recording', 'Mach dich bereit. Sprich ab dem ersten Buchstaben ein Codewort pro Takt.');
    el('prompt').scrollIntoView({behavior: 'smooth', block: 'center'});
    function tick() {
        const elapsed = performance.now() - started - countdown;
        if (elapsed < 0) {
            const remaining = Math.ceil(-elapsed / 1000);
            el('prompt').textContent = remaining === 1 ? 'Go!' : remaining - 1;
            el('gameRound').textContent = 'Bereit?';
            el('gameClock').value = 0;
            return;
        }
        const index = Math.floor(elapsed / game.interval);
        if (index >= 10) {
            clearInterval(clock);
            el('prompt').textContent = '✓';
            el('recordStatus').textContent = 'Alle zehn Buchstaben aufgenommen. Audio wird ausgewertet …';
            stopRecording();
            return;
        }
        game.round = index + 1;
        el('prompt').textContent = task.prompt[index];
        el('recordStatus').textContent = `Buchstabe ${index + 1} von 10 · Jetzt das Codewort sprechen!`;
        el('gameClock').value = game.interval - elapsed % game.interval;
        renderGame();
    }
    tick();
    clock = setInterval(tick, 40);
}

function finishGame(result) {
    game.active = false;
    el('gameSummaryTitle').textContent = `${result.correct} von 10 richtig · ${result.score} %`;
    el('gameSummaryText').textContent = result.passed
        ? 'Challenge geschafft! Alle zehn Codewörter in der richtigen Reihenfolge.'
        : 'Deine Aufnahme ist ausgewertet. Unten siehst du den Vergleich für jeden Buchstaben.';
    el('gameSummary').hidden = false;
    renderGame();
    el('gameProcessing').hidden = true;
    el('gameSummaryTitle').focus({preventScroll: true});
    el('gameSummary').scrollIntoView({behavior: 'smooth', block: 'start'});
}

function cancelGame() {
    cancelling = true;
    if (recorder && recorder.state === 'recording') recorder.stop();
    releaseStream();
    game.active = false;
    renderGame();
    setPhase('ready', 'Spiel abgebrochen. Keine Auswertung.');
    nextTask();
}

function toggleAlphabet() {
    const visible = el('alphabetPanel').hidden;
    el('alphabetPanel').hidden = !visible;
    el('alphabetToggle').setAttribute('aria-expanded', String(visible));
    el('alphabetToggle').textContent = visible ? 'NATO-Alphabet ausblenden' : 'NATO-Alphabet einblenden';
    if (visible && game.active && !game.graded) {
        game.hinted = true;
        renderGame();
    }
}

el('alphabetToggle').onclick = toggleAlphabet;
el('alphabetClose').onclick = () => { toggleAlphabet(); el('alphabetToggle').focus(); };
el('gameStart').onclick = startGame;
el('playAgain').onclick = startGame;
el('gameEnd').onclick = cancelGame;
window.addEventListener('pagehide', () => {
    cancelling = true;
    clearTimeout(pollTimer);
    releaseStream();
});

async function initialize() {
    try {
        alphabet = await request('/api/trainer/alphabet');
        el('alphabet').replaceChildren(...Object.entries(alphabet).map(([letter, word]) => {
            const entry = document.createElement('div');
            const label = document.createElement('b');
            label.textContent = letter;
            entry.append(label, document.createTextNode(word));
            return entry;
        }));
        await nextTask();
    } catch (error) {
        fail(error);
        el('next').disabled = false;
        el('next').textContent = 'Verbindung erneut versuchen →';
        el('next').onclick = async () => { el('next').onclick = nextTask; await initialize(); };
    }
}
initialize();
