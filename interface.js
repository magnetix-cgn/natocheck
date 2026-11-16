'use strict';

// Interface language is independent of the fixed English recognizer.
const interfaceTranslations = {
    "ERKENNUNG UNSICHER": "UNCERTAIN RECOGNITION",
    "Noch keine Wertung. Bitte den erkannten Text prüfen.": "Not scored yet. Please review the recognized text.",
    "Aufnahme angekommen. Bitte die unsichere Erkennung prüfen oder erneut aufnehmen.": "Recording received. Please review the uncertain transcript or record again.",
    "NatoCheck · Buchstabieren. Sprechen. Checken.": "NatoCheck · Spell. Speak. Check.",
    "NatoCheck Startseite": "NatoCheck home",
    "NATO-Alphabet einblenden": "Show NATO alphabet",
    "NATO-Alphabet ausblenden": "Hide NATO alphabet",
    "DEIN ERGEBNIS": "YOUR RESULT",
    "Noch eine Runde →": "Play again →",
    "ALFA BIS ZULU / DEIN FUNK-CHECK": "ALFA TO ZULU / YOUR RADIO CHECK",
    "Dein Mikrofon. Dein Takt.": "Your microphone. Your pace.",
    "Dein NATO-Check.": "Your NATO check.",
    "Spiel starten. 3, 2, 1, Go! Sprich die NATO-Codewörter zu zehn Buchstaben. Dein Ergebnis kommt nach dem letzten Buchstaben.": "Start the game. 3, 2, 1, Go! Say the NATO codewords for ten letters. Your result appears after the last letter.",
    "Das NATO-Alphabet": "The NATO alphabet",
    "Schließen ×": "Close ×",
    "Schreibvarianten wie Alpha/Alfa, Juliet/Juliett und Fox Trot/Foxtrot werden akzeptiert. Zusätzliche Wörter und falsche Reihenfolgen zählen als Abweichung.": "Spelling variants such as Alpha/Alfa, Juliet/Juliett and Fox Trot/Foxtrot are accepted. Extra words and incorrect order count as errors.",
    "Mehr zum NATO-Alphabet ↗": "More about the NATO alphabet ↗",
    "LUST AUF EINE CHALLENGE?": "READY FOR A CHALLENGE?",
    "10 Buchstaben. Ein Takt. Eine Challenge.": "10 letters. One pace. One challenge.",
    "Sprich zu jedem Buchstaben das NATO-Codewort. Wir nehmen den ganzen Lauf auf und werten erst danach aus.": "Say the NATO codeword for each letter. We record the entire round and evaluate it afterwards.",
    "Geschwindigkeit": "Speed",
    "Entspannt · 5 Sekunden": "Relaxed · 5 seconds",
    "Normal · 3 Sekunden": "Normal · 3 seconds",
    "Schnell · 2 Sekunden": "Fast · 2 seconds",
    "Profi · 1 Sekunde": "Expert · 1 second",
    "Spiel starten →": "Start game →",
    "Spielmodus": "Game mode",
    "Spielstand": "Game progress",
    "BUCHSTABE": "LETTER",
    "TAKT": "PACE",
    "Spiel abbrechen": "Cancel game",
    "Zeit für den aktuellen Buchstaben": "Time for the current letter",
    "Auswertung läuft …": "Evaluating …",
    "Alle zehn Buchstaben sind aufgenommen. Deine Codewörter werden jetzt gemeinsam erkannt und verglichen.": "All ten letters have been recorded. Your codewords are now being recognized and compared together.",
    "02 / CHECKEN": "02 / CHECK",
    "Das ist angekommen": "What we heard",
    "SPRACHERKENNUNG": "SPEECH RECOGNITION",
    "Buchstabe": "Letter",
    "Erwartet": "Expected",
    "Erkannt": "Recognized",
    "Passt der erkannte Text zu deiner Antwort? Bestätige die Wertung oder nimm bei einem Erkennungsfehler erneut auf.": "Does the recognized text match your answer? Confirm the score or record again if recognition was incorrect.",
    "Ergebnis werten →": "Confirm score →",
    "Erkennung falsch? Text korrigieren": "Recognition incorrect? Edit the text",
    "Was du tatsächlich gesagt hast": "What you actually said",
    "Zum Beispiel: Alfa Bravo Charlie": "For example: Alfa Bravo Charlie",
    "Korrigierten Text prüfen": "Check corrected text",
    "Die erneute Prüfung wird als manuell korrigiert markiert.": "The new result is marked as manually corrected.",
    "Dein Spielfeld": "Your training area",
    "Übungsart": "Exercise type",
    "Wort": "Word",
    "Zeichenfolge": "Sequence",
    "Sag das passende Codewort für jeden Buchstaben.": "Say the correct codeword for each letter.",
    "Lösung zeigen": "Show answer",
    "Nächste Aufgabe →": "Next exercise →",
    "Antwort aufnehmen": "Record answer",
    "Stoppen & prüfen": "Stop & check",
    "Trainer wird verbunden …": "Connecting to trainer …",
    "Erkennung immer auf Englisch mit dem Standardmikrofon. Aufnahme nur nach deinem Klick, maximal 60 Sekunden und 2 MB. Verarbeitung auf diesem App-Server; die Aufnahme wird nach der Erkennung gelöscht.": "Recognition always uses English and the default microphone. Recording starts only after your click, up to 60 seconds and 2 MB. Processing takes place on this app server; the recording is deleted after recognition.",
    "Deine letzte Aufnahme": "Your last recording",
    "Ohne Mikrofon üben": "Practice without a microphone",
    "Du kannst die Codewörter auch eingeben und prüfen lassen.": "You can also type the codewords and check your answer.",
    "Deine Antwort": "Your answer",
    "NATO-Codewörter eingeben …": "Enter NATO codewords …",
    "Textantwort prüfen": "Check typed answer",
    "NatoCheck unterstützen ❤️": "Support NatoCheck ❤️",
    "FREIWILLIG": "OPTIONAL",
    "NatoCheck bleibt kostenlos und Open Source. Server und Spracherkennung werden privat finanziert und stoßen manchmal an ihre Grenzen. Mit einem freiwilligen Beitrag hilfst du, die Infrastruktur zu verbessern.": "NatoCheck remains free and open source. Servers and speech recognition are privately funded and sometimes reach their limits. An optional contribution helps improve the infrastructure.",
    "Per PayPal unterstützen ↗": "Support via PayPal ↗",
    "Open Source. Deine Idee zählt.": "Open source. Your ideas matter.",
    "Du willst NatoCheck verändern, hast eine Idee oder einen Fehler gefunden? Schick uns einen Task oder Change Request als GitHub-Issue. Du kannst den Code auch selbst ändern und einen Pull Request einreichen.": "Want to change NatoCheck, suggest an idea or report a bug? Send us a task or change request as a GitHub issue. You can also change the code and submit a pull request.",
    "NatoCheck · Ein Eventhacker-Experiment.": "NatoCheck · An Eventhacker experiment.",
    "Verglichen wird der erkannte Text, nicht die Aussprache.": "We compare recognized text, not pronunciation.",
    "Anfrage fehlgeschlagen.": "Request failed.",
    "Nächste Runde →": "Next round →",
    "Keine Wertung. Bitte erneut versuchen.": "No score. Please try again.",
    "Neue Aufgabe …": "New exercise …",
    "Bereit. Sprich die Codewörter in der angezeigten Reihenfolge.": "Ready. Say the codewords in the displayed order.",
    "Verbindung erneut versuchen →": "Retry connection →",
    "Antwort wird verglichen …": "Checking your answer …",
    "MANUELL KORRIGIERT": "MANUALLY CORRECTED",
    "TEXTEINGABE": "TYPED ANSWER",
    "Check! Alles richtig.": "Check! All correct.",
    "Richtig": "Correct",
    "Abweichung": "Incorrect",
    "Fehlt": "Missing",
    "Zusätzlich": "Extra",
    "Prüfung abgeschlossen. Wiederholen oder nächste Aufgabe wählen.": "Check complete. Try again or choose the next exercise.",
    "Aufnahme wird vorbereitet …": "Preparing recording …",
    "Die Aufnahme wurde durch einen anderen Vorgang ersetzt. Bitte erneut aufnehmen.": "The recording was replaced by another request. Please record again.",
    "Die Aufnahme konnte nicht gelesen werden. Bitte erneut aufnehmen. Wenn es wieder passiert, die Aufnahme über den Audioplayer sichern und zur Fehlerprüfung bereitstellen.": "The recording could not be read. Please record again. If this happens again, save the recording from the audio player and provide it for investigation.",
    "Mikrofon wird aktiviert …": "Activating microphone …",
    "Mikrofonaufnahme benötigt Chromium und eine lokale Adresse oder HTTPS.": "Recording requires a compatible browser on localhost or HTTPS.",
    "Kein unterstütztes Aufnahmeformat verfügbar.": "No supported recording format is available.",
    "Aufnahme fehlgeschlagen.": "Recording failed.",
    "Die Aufnahme überschreitet das Limit von 2 MB. Bitte kürzer aufnehmen.": "The recording exceeds the 2 MB limit. Please make a shorter recording.",
    "Die Aufnahme ist leer.": "The recording is empty.",
    "Aufnahme konnte nicht verarbeitet werden.": "The recording could not be processed.",
    "Auswertung läuft … Deine Aufnahme wird erkannt und anschließend verglichen.": "Evaluating … Your recording is being recognized and will then be compared.",
    "Mikrofonzugriff nicht erlaubt. Bitte im Browser freigeben oder per Texteingabe üben.": "Microphone access was denied. Allow access in your browser or practice with typed answers.",
    "Zehn Buchstaben werden vorbereitet …": "Preparing ten letters …",
    "Mach dich bereit. Sprich ab dem ersten Buchstaben ein Codewort pro Takt.": "Get ready. Starting with the first letter, say one codeword per beat.",
    "Bereit?": "Ready?",
    "Alle zehn Buchstaben aufgenommen. Audio wird ausgewertet …": "All ten letters recorded. Evaluating audio …",
    "Challenge geschafft! Alle zehn Codewörter in der richtigen Reihenfolge.": "Challenge complete! All ten codewords in the correct order.",
    "Deine Aufnahme ist ausgewertet. Unten siehst du den Vergleich für jeden Buchstaben.": "Your recording has been evaluated. The comparison for each letter is shown below.",
    "Spiel abgebrochen. Keine Auswertung.": "Game cancelled. No score."
};

let interfaceLanguage = 'de';
try {
    const requested = new URLSearchParams(location.search).get('lang');
    const saved = localStorage.getItem('natocheck.interfaceLanguage');
    interfaceLanguage = ['de', 'en'].includes(requested) ? requested : (saved === 'en' ? 'en' : 'de');
} catch (_) { /* German remains available when storage is blocked. */ }

function translate(text) {
    if (interfaceLanguage !== 'en') return text;
    const trimmed = text.trim();
    if (interfaceTranslations[trimmed]) return text.replace(trimmed, interfaceTranslations[trimmed]);
    const patterns = [
        [/^(\d+) von (\d+) Codewörtern richtig · (\d+) %$/, '$1 of $2 codewords correct · $3 %'],
        [/^(\d+) von 10 richtig · (\d+) %$/, '$1 of 10 correct · $2 %'],
        [/^Aufnahme läuft · (\d+) \/ 60 Sekunden$/, 'Recording · $1 / 60 seconds'],
        [/^Buchstabe (\d+) von 10 · Jetzt das Codewort sprechen!$/, 'Letter $1 of 10 · Say the codeword now!'],
        [/^(\d+) s \/ Buchstabe$/, '$1 s / letter'],
        [/^Lösung: /, 'Answer: '],
        [/^Auswertung abgeschlossen · (.+) Sekunden Erkennungszeit$/, 'Evaluation complete · $1 seconds recognition time'],
        [/ Erkennungszeit: (.+) Sekunden\.$/, ' Recognition time: $1 seconds.'],
        [/^Auswertung fehlgeschlagen\. /, 'Evaluation failed. '],
    ];
    let result = text;
    for (const [german, english] of Object.entries(interfaceTranslations)) {
        if (text.startsWith(german + ' Erkennungszeit:')) {
            result = english + text.slice(german.length);
            break;
        }
    }
    for (const [pattern, replacement] of patterns) result = result.replace(pattern, replacement);
    return result;
}

const localizedElements = new Map();
function uiText(target, text) {
    const element = typeof target === 'string' ? document.getElementById(target) : target;
    localizedElements.set(element, String(text));
    element.textContent = translate(String(text));
}

// Keep original text nodes so switching never replaces controls or user input.
const staticTexts = [];
const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
while (walker.nextNode()) {
    const node = walker.currentNode;
    if (!node.parentElement.closest('script, style') && node.textContent.trim()) {
        staticTexts.push([node, node.textContent]);
    }
}
const staticAttributes = [];
document.querySelectorAll('[aria-label], [placeholder]').forEach(element => {
    for (const attribute of ['aria-label', 'placeholder']) {
        if (element.hasAttribute(attribute)) staticAttributes.push([element, attribute, element.getAttribute(attribute)]);
    }
});
const originalTitle = document.title;
function applyInterfaceLanguage() {
    document.documentElement.lang = interfaceLanguage;
    document.title = translate(originalTitle);
    for (const [node, original] of staticTexts) {
        if (node.isConnected) node.textContent = translate(original);
    }
    for (const [element, attribute, original] of staticAttributes) element.setAttribute(attribute, translate(original));
    for (const [element, original] of localizedElements) {
        if (element.isConnected) element.textContent = translate(original);
        else localizedElements.delete(element);
    }
    document.querySelectorAll('[data-ui-language]').forEach(button => {
        button.setAttribute('aria-pressed', String(button.dataset.uiLanguage === interfaceLanguage));
    });
    document.dispatchEvent(new Event('interfacelanguagechange'));
}
document.querySelectorAll('[data-ui-language]').forEach(button => {
    button.addEventListener('click', () => {
        interfaceLanguage = button.dataset.uiLanguage;
        try { localStorage.setItem('natocheck.interfaceLanguage', interfaceLanguage); } catch (_) { /* Storage is optional. */ }
        const url = new URL(location.href);
        url.searchParams.set('lang', interfaceLanguage);
        history.replaceState(null, '', url);
        applyInterfaceLanguage();
    });
});
applyInterfaceLanguage();
