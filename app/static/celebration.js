class Celebration {
    constructor() {
        this.container = document.querySelector('.celebration-container');
        this.roseCount = 100;
        this.roses = [];
    }

    start() {
        this.container.style.display = 'block';
        
        // Create win text
        const winText = document.createElement('div');
        winText.className = 'win-text';
        winText.textContent = 'YOU WIN!';
        this.container.appendChild(winText);
        
        setTimeout(() => winText.remove(), 4000);
        
        this.createInitialBatch();
        this.createRemainingRoses();
    }

    createInitialBatch() {
        for (let i = 0; i < 20; i++) {
            this.createSingleRose(true);
        }
    }

    createRemainingRoses() {
        for (let i = 0; i < this.roseCount - 20; i++) {
            setTimeout(() => this.createSingleRose(false), i * 50);
        }
    }

    createSingleRose(isInitial) {
        const rose = document.createElement('div');
        rose.className = `rose ${this.getRandomSize()} floating`;
        
        const startX = Math.random() * window.innerWidth;
        const startY = isInitial ? 
            Math.random() * window.innerHeight : 
            window.innerHeight + 50;
            
        rose.style.left = `${startX}px`;
        rose.style.top = `${startY}px`;
        
        this.container.appendChild(rose);
        rose.addEventListener('animationend', () => rose.remove());
    }

    getRandomSize() {
        return ['medium', 'large', 'large'][Math.floor(Math.random() * 3)];
    }
}

// Create the celebration instance and attach it to window
document.addEventListener('DOMContentLoaded', () => {
    if (!document.querySelector('.celebration-container')) {
        const container = document.createElement('div');
        container.className = 'celebration-container';
        document.body.appendChild(container);
    }
    window.gameCelebration = new Celebration();
});