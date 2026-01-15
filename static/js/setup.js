/**
 * DataReady.io - Setup Page JavaScript
 * 
 * Handles:
 * - Form interactions
 * - Interview session creation
 * - Navigation to interview room
 */

// ============================================================================
// Toast Notification System
// ============================================================================

const Toast = {
    container: null,
    
    init() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            this.container.id = 'toast-container';
            document.body.appendChild(this.container);
        }
    },
    
    show(message, type = 'info', duration = 5000) {
        this.init();
        
        const icons = {
            error: '⚠️',
            success: '✓',
            warning: '⚡',
            info: 'ℹ️'
        };
        
        const titles = {
            error: 'Error',
            success: 'Success',
            warning: 'Warning',
            info: 'Info'
        };
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.style.position = 'relative';
        toast.innerHTML = `
            <span class="toast-icon">${icons[type]}</span>
            <div class="toast-content">
                <div class="toast-title">${titles[type]}</div>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close" onclick="Toast.dismiss(this.parentElement)">×</button>
            <div class="toast-progress" style="animation-duration: ${duration}ms"></div>
        `;
        
        this.container.appendChild(toast);
        
        // Auto-dismiss after duration
        setTimeout(() => this.dismiss(toast), duration);
        
        return toast;
    },
    
    dismiss(toast) {
        if (!toast || !toast.parentElement) return;
        
        toast.classList.add('toast-exit');
        setTimeout(() => {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 300);
    },
    
    error(message, duration = 6000) {
        return this.show(message, 'error', duration);
    },
    
    success(message, duration = 4000) {
        return this.show(message, 'success', duration);
    },
    
    warning(message, duration = 5000) {
        return this.show(message, 'warning', duration);
    },
    
    info(message, duration = 4000) {
        return this.show(message, 'info', duration);
    }
};

// ============================================================================
// DOM Elements
// ============================================================================

const setupForm = document.getElementById('setup-form');
const experienceSlider = document.getElementById('experience');
const experienceValue = document.getElementById('experience-value');
const questionsSlider = document.getElementById('questions');
const questionsValue = document.getElementById('questions-value');
const startBtn = document.getElementById('start-btn');

// ============================================================================
// Slider Handlers
// ============================================================================

function updateSliderValues() {
    experienceValue.textContent = `${experienceSlider.value} years`;
    questionsValue.textContent = `${questionsSlider.value} questions`;
}

experienceSlider.addEventListener('input', updateSliderValues);
questionsSlider.addEventListener('input', updateSliderValues);

// Initialize
updateSliderValues();

// ============================================================================
// Form Submission
// ============================================================================

setupForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Disable button and show loading
    startBtn.disabled = true;
    startBtn.querySelector('.btn-text').textContent = 'Setting up...';
    
    try {
        // Gather form data
        const formData = new FormData(setupForm);
        
        const payload = {
            years_of_experience: parseInt(formData.get('experience') || '3'),
            target_role: formData.get('role') || 'mid_data_engineer',
            cloud_preference: formData.get('cloud') || 'cloud_agnostic',
            mode: formData.get('mode') || 'structured_followup',
            max_questions: parseInt(formData.get('questions') || '10'),
            include_skills: [],
            exclude_skills: [],
        };
        
        // Create interview session
        const response = await fetch('/api/interview/setup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create interview');
        }
        
        const data = await response.json();
        
        // Store session info
        sessionStorage.setItem('sessionId', data.session_id);
        sessionStorage.setItem('interviewSetup', JSON.stringify(payload));
        
        // Navigate to interview room
        window.location.href = `/interview/${data.session_id}`;
        
    } catch (error) {
        console.error('Setup error:', error);
        Toast.error(error.message || 'Failed to create interview session');
        
        // Reset button
        startBtn.disabled = false;
        startBtn.querySelector('.btn-text').textContent = 'Begin Interview';
    }
});

// ============================================================================
// Role Card Interactions
// ============================================================================

const roleCards = document.querySelectorAll('.role-card input');

roleCards.forEach(card => {
    card.addEventListener('change', () => {
        // Update visual feedback
        document.querySelectorAll('.role-card').forEach(c => {
            c.classList.remove('selected');
        });
        card.closest('.role-card').classList.add('selected');
        
        // Suggest experience based on role
        const roleExperience = {
            'junior_data_engineer': 1,
            'mid_data_engineer': 3,
            'senior_data_engineer': 6,
            'staff_data_engineer': 10,
        };
        
        const suggested = roleExperience[card.value] || 3;
        experienceSlider.value = suggested;
        updateSliderValues();
    });
});

// ============================================================================
// Cloud Option Interactions
// ============================================================================

const cloudOptions = document.querySelectorAll('.cloud-option input');

cloudOptions.forEach(option => {
    option.addEventListener('change', () => {
        document.querySelectorAll('.cloud-option').forEach(o => {
            o.classList.remove('selected');
        });
        option.closest('.cloud-option').classList.add('selected');
    });
});

// ============================================================================
// Mode Option Interactions
// ============================================================================

const modeOptions = document.querySelectorAll('.mode-option input');

modeOptions.forEach(option => {
    option.addEventListener('change', () => {
        document.querySelectorAll('.mode-option').forEach(o => {
            o.classList.remove('selected');
        });
        option.closest('.mode-option').classList.add('selected');
    });
});

// ============================================================================
// Keyboard Navigation
// ============================================================================

document.addEventListener('keydown', (e) => {
    // Enter to submit (when not in a text field)
    if (e.key === 'Enter' && e.target.tagName !== 'INPUT') {
        setupForm.dispatchEvent(new Event('submit'));
    }
});

// ============================================================================
// Initialize Animations
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Add staggered animation to form sections
    const sections = document.querySelectorAll('.form-section');
    sections.forEach((section, index) => {
        section.style.animationDelay = `${0.3 + index * 0.1}s`;
        section.classList.add('fade-in');
    });
});
