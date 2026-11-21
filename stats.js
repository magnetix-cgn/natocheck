'use strict';

let usageStats = null;

function renderStats() {
    const ids = ['statsCompleted', 'statsToday', 'statsPerfect'];
    if (!usageStats) {
        ids.forEach(id => { document.getElementById(id).textContent = '—'; });
        uiText('statsStatus', 'Nutzungszahlen sind gerade nicht verfügbar.');
        document.getElementById('statsSince').textContent = '';
        return;
    }
    const locale = interfaceLanguage === 'en' ? 'en-GB' : 'de-DE';
    const number = new Intl.NumberFormat(locale);
    [usageStats.completed, usageStats.today_completed, usageStats.perfect].forEach((value, index) => {
        document.getElementById(ids[index]).textContent = number.format(value);
    });
    const stamp = new Intl.DateTimeFormat(locale, {dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Berlin'});
    document.getElementById('statsStatus').textContent = (interfaceLanguage === 'en' ? 'Updated: ' : 'Stand: ') + stamp.format(new Date(usageStats.as_of));
    document.getElementById('statsSince').textContent = (interfaceLanguage === 'en' ? 'Counted since ' : 'Erfasst seit ') + stamp.format(new Date(usageStats.since)) + '.';
}

async function refreshStats() {
    try {
        const response = await fetch('/api/stats', {cache: 'no-store'});
        if (!response.ok) throw Error('Statistics unavailable');
        const data = await response.json();
        if (![data.completed, data.today_completed, data.perfect].every(value => Number.isSafeInteger(value) && value >= 0)
                || data.perfect > data.completed || data.today_completed > data.completed
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
