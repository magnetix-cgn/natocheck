'use strict';

const trainingToggle = document.getElementById('trainingToggle');
const trainingPanel = document.getElementById('trainingPanel');
const trainingVideo = document.getElementById('trainingVideo');
const trainingPlay = document.getElementById('trainingPlay');
const trainingError = document.getElementById('trainingError');

function playTraining() {
    trainingError.hidden = true;
    trainingVideo.focus();
    trainingVideo.play().catch(() => {
        trainingPlay.hidden = false;
        trainingError.hidden = false;
    });
}

trainingToggle.addEventListener('click', () => {
    playTraining();
    trainingPanel.scrollIntoView({block: 'center'});
    trainingVideo.focus();
});
trainingPlay.addEventListener('click', playTraining);
trainingVideo.addEventListener('play', () => { trainingPlay.hidden = true; });
trainingVideo.addEventListener('pause', () => { trainingPlay.hidden = false; });
trainingVideo.addEventListener('ended', () => { trainingPlay.hidden = false; });
document.getElementById('gameStart').addEventListener('click', () => {
    trainingVideo.pause();
});
document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && trainingPanel.contains(document.activeElement) && !document.fullscreenElement) {
        trainingVideo.pause();
        trainingToggle.focus();
    }
});
