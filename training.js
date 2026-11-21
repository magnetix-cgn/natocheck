'use strict';

const trainingPanel = document.getElementById('trainingPanel');
const trainingVideo = document.getElementById('trainingVideo');
const trainingPlay = document.getElementById('trainingPlay');
const trainingError = document.getElementById('trainingError');

function playTraining() {
    trainingError.hidden = true;
    // An explicit Play action must not inherit a muted or zero-volume state.
    trainingVideo.defaultMuted = false;
    trainingVideo.muted = false;
    if (trainingVideo.volume === 0) trainingVideo.volume = 1;
    trainingVideo.focus();
    trainingVideo.play().catch(() => {
        trainingPlay.hidden = false;
        trainingError.hidden = false;
    });
}

trainingPlay.addEventListener('click', playTraining);
document.getElementById('trainingSound').addEventListener('click', () => {
    trainingVideo.volume = 1;
    playTraining();
});
trainingVideo.addEventListener('play', () => { trainingPlay.hidden = true; });
trainingVideo.addEventListener('pause', () => { trainingPlay.hidden = false; });
trainingVideo.addEventListener('ended', () => { trainingPlay.hidden = false; });
document.getElementById('gameStart').addEventListener('click', () => {
    trainingVideo.pause();
});
document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && trainingPanel.contains(document.activeElement) && !document.fullscreenElement) {
        trainingVideo.pause();
        trainingPlay.hidden = false;
        trainingPlay.focus();
    }
});
