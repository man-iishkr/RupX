// Custom Cursor with Cool Lighting Animation
const cursor = document.querySelector('.cursor');
const cursorFollower = document.querySelector('.cursor-follower');

// Create cursor glow element
const cursorGlow = document.createElement('div');
cursorGlow.className = 'cursor-glow';
document.body.appendChild(cursorGlow);

let mouseX = 0;
let mouseY = 0;
let cursorX = 0;
let cursorY = 0;
let followerX = 0;
let followerY = 0;
let glowX = 0;
let glowY = 0;

document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
});

function animateCursor() {
    // Smooth cursor movement
    const distX = mouseX - cursorX;
    const distY = mouseY - cursorY;
    
    cursorX += distX * 0.3;
    cursorY += distY * 0.3;
    
    cursor.style.left = cursorX + 'px';
    cursor.style.top = cursorY + 'px';
    
    // Follower with delay
    const followerDistX = mouseX - followerX;
    const followerDistY = mouseY - followerY;
    
    followerX += followerDistX * 0.1;
    followerY += followerDistY * 0.1;
    
    cursorFollower.style.left = followerX - 20 + 'px';
    cursorFollower.style.top = followerY - 20 + 'px';
    
    // Glow effect with more delay
    const glowDistX = mouseX - glowX;
    const glowDistY = mouseY - glowY;
    
    glowX += glowDistX * 0.05;
    glowY += glowDistY * 0.05;
    
    cursorGlow.style.left = glowX + 'px';
    cursorGlow.style.top = glowY + 'px';
    
    requestAnimationFrame(animateCursor);
}

animateCursor();

// Cursor scale and color change on hover
const hoverElements = document.querySelectorAll('a, button, .feature-card, .step, input, textarea');

hoverElements.forEach(el => {
    el.addEventListener('mouseenter', () => {
        cursor.style.transform = 'scale(2)';
        cursor.style.background = '#ffb088';
        cursor.style.boxShadow = '0 0 30px #ffb088';
        cursorFollower.style.transform = 'scale(1.5)';
        cursorFollower.style.borderColor = 'rgba(255, 176, 136, 0.8)';
        cursorGlow.style.background = 'radial-gradient(circle, rgba(255, 176, 136, 0.25) 0%, transparent 70%)';
    });
    
    el.addEventListener('mouseleave', () => {
        cursor.style.transform = 'scale(1)';
        cursor.style.background = '#ff7849';
        cursor.style.boxShadow = '0 0 20px #ff7849';
        cursorFollower.style.transform = 'scale(1)';
        cursorFollower.style.borderColor = 'rgba(255, 120, 73, 0.5)';
        cursorGlow.style.background = 'radial-gradient(circle, rgba(255, 120, 73, 0.15) 0%, transparent 70%)';
    });
});

// Click effect
document.addEventListener('mousedown', () => {
    cursor.style.transform = 'scale(0.8)';
    cursorFollower.style.transform = 'scale(1.2)';
    
    // Create ripple effect
    const ripple = document.createElement('div');
    ripple.style.position = 'fixed';
    ripple.style.left = mouseX + 'px';
    ripple.style.top = mouseY + 'px';
    ripple.style.width = '10px';
    ripple.style.height = '10px';
    ripple.style.borderRadius = '50%';
    ripple.style.border = '2px solid #ff7849';
    ripple.style.pointerEvents = 'none';
    ripple.style.zIndex = '9997';
    ripple.style.transform = 'translate(-50%, -50%)';
    ripple.style.animation = 'ripple 0.6s ease-out';
    
    document.body.appendChild(ripple);
    
    setTimeout(() => ripple.remove(), 600);
});

document.addEventListener('mouseup', () => {
    cursor.style.transform = 'scale(1)';
    cursorFollower.style.transform = 'scale(1)';
});

// Add ripple animation
const style = document.createElement('style');
style.textContent = `
    @keyframes ripple {
        0% {
            width: 10px;
            height: 10px;
            opacity: 1;
        }
        100% {
            width: 80px;
            height: 80px;
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);