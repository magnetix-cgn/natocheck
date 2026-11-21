'use strict';

const trainingToggle = document.getElementById('trainingToggle');
const trainingPanel = document.getElementById('trainingPanel');
const trainingVideo = document.getElementById('trainingVideo');

function closeTraining() {
    trainingVideo.pause();
    trainingPanel.hidden = true;
    trainingToggle.setAttribute('aria-expanded', 'false');
}

trainingToggle.addEventListener('click', () => {
    if (!trainingPanel.hidden) {
        closeTraining();
        return;
    }
    trainingPanel.hidden = false;
    trainingToggle.setAttribute('aria-expanded', 'true');
    if (!trainingVideo.getAttribute('src')) trainingVideo.src = trainingVideo.dataset.src;
    trainingVideo.focus();
});
document.getElementById('trainingClose').addEventListener('click', () => {
    closeTraining();
    trainingToggle.focus();
});
document.getElementById('gameStart').addEventListener('click', closeTraining);
document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !trainingPanel.hidden && !document.fullscreenElement) {
        closeTraining();
        trainingToggle.focus();
    }
});
