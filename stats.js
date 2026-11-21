'use strict';

let usageStats = null;
const statsSpeeds = [1000, 2000, 3000, 5000];

function renderStats() {
    const ids = ['statsCompleted', 'statsToday', 'statsPerfect'];
    if (!usageStats) {
        [...ids, 'statsAverage', ...statsSpeeds.flatMap(speed => ['statsSpeed' + speed, 'statsAverage' + speed])]
            .forEach(id => { document.getElementById(id).textContent = '—'; });
        uiText('statsStatus', 'Nutzungszahlen sind gerade nicht verfügbar.');
        document.getElementById('statsSince').textContent = '';
        document.getElementById('statsDetailsSince').textContent = '';
        return;
    }
    const locale = interfaceLanguage === 'en' ? 'en-GB' : 'de-DE';
    const number = new Intl.NumberFormat(locale);
    const percent = new Intl.NumberFormat(locale, {style: 'percent', maximumFractionDigits: 1});
    const average = value => value === null ? '—' : percent.format(value / 100);
    document.getElementById('statsAverage').textContent = average(usageStats.average_score);
    statsSpeeds.forEach(speed => {
        const counts = usageStats.by_speed[speed];
        document.getElementById('statsSpeed' + speed).textContent = number.format(counts.completed);
        document.getElementById('statsAverage' + speed).textContent = average(counts.average_score);
    });
    [usageStats.completed, usageStats.today_completed, usageStats.perfect].forEach((value, index) => {
        document.getElementById(ids[index]).textContent = number.format(value);
    });
    const stamp = new Intl.DateTimeFormat(locale, {dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Berlin'});
    document.getElementById('statsStatus').textContent = (interfaceLanguage === 'en' ? 'Updated: ' : 'Stand: ') + stamp.format(new Date(usageStats.as_of));
    document.getElementById('statsSince').textContent = (interfaceLanguage === 'en' ? 'Counted since ' : 'Erfasst seit ') + stamp.format(new Date(usageStats.since)) + '.';
    document.getElementById('statsDetailsSince').textContent = interfaceLanguage === 'en'
        ? `Pace and scores recorded since ${stamp.format(new Date(usageStats.details_since))}. Average based on ${number.format(usageStats.scored_completed)} challenges. Games without a recorded pace: ${number.format(usageStats.unclassified_completed)}.`
        : `Tempo und Trefferquote erfasst seit ${stamp.format(new Date(usageStats.details_since))}. Durchschnitt aus ${number.format(usageStats.scored_completed)} Challenges. Spiele ohne erfasstes Tempo: ${number.format(usageStats.unclassified_completed)}.`;
}

async function refreshStats() {
    try {
        const response = await fetch('/api/stats', {cache: 'no-store'});
        if (!response.ok) throw Error('Statistics unavailable');
        const data = await response.json();
        const validCount = value => Number.isSafeInteger(value) && value >= 0;
        const validAverage = (value, count) => count === 0 ? value === null : Number.isFinite(value) && value >= 0 && value <= 100;
        if (![data.completed, data.today_completed, data.perfect].every(value => Number.isSafeInteger(value) && value >= 0)
                || data.perfect > data.completed || data.today_completed > data.completed
                || !validCount(data.scored_completed) || data.scored_completed > data.completed
                || !validCount(data.unclassified_completed) || data.unclassified_completed > data.completed
                || !validAverage(data.average_score, data.scored_completed)
                || !statsSpeeds.every(speed => data.by_speed?.[speed]
                    && validCount(data.by_speed[speed].completed)
                    && validAverage(data.by_speed[speed].average_score, data.by_speed[speed].completed))
                || statsSpeeds.reduce((total, speed) => total + data.by_speed[speed].completed, 0) + data.unclassified_completed !== data.completed
                || !Number.isFinite(Date.parse(data.details_since))
                || !Number.isFinite(Date.parse(data.since)) || !Number.isFinite(Date.parse(data.as_of))) {
            throw Error('Invalid statistics');
        }
        usageStats = data;
    } catch (_) {
        usageStats = null;
    }
    renderStats();
}

document.addEventListener('interfacelanguagechange', renderStats);
document.addEventListener('challengecomplete', refreshStats);
document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshStats(); });
setInterval(() => { if (!document.hidden) refreshStats(); }, 60000);
refreshStats();
