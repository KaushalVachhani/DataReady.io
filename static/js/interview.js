/**
 * DataReady.io - Interview Room JavaScript
 * 
 * Handles:
 * - WebSocket communication
 * - Audio recording
 * - Webcam display
 * - Interview flow
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
// Modal Confirmation System
// ============================================================================

const Modal = {
    show(options) {
        return new Promise((resolve) => {
            const {
                title = 'Confirm',
                message = 'Are you sure?',
                confirmText = 'Confirm',
                cancelText = 'Cancel',
                type = 'warning', // 'warning', 'danger', 'info'
                icon = '⚠️'
            } = options;
            
            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-icon modal-icon-${type}">${icon}</div>
                    <h2 class="modal-title">${title}</h2>
                    <p class="modal-message">${message}</p>
                    <div class="modal-actions">
                        <button class="modal-btn modal-btn-cancel">${cancelText}</button>
                        <button class="modal-btn ${type === 'danger' ? 'modal-btn-danger' : 'modal-btn-confirm'}">${confirmText}</button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(overlay);
            
            // Focus the confirm button
            const confirmBtn = overlay.querySelector('.modal-btn-confirm, .modal-btn-danger');
            const cancelBtn = overlay.querySelector('.modal-btn-cancel');
            
            const close = (result) => {
                overlay.classList.add('modal-exit');
                setTimeout(() => {
                    if (overlay.parentElement) {
                        overlay.parentElement.removeChild(overlay);
                    }
                    resolve(result);
                }, 200);
            };
            
            confirmBtn.addEventListener('click', () => close(true));
            cancelBtn.addEventListener('click', () => close(false));
            
            // Close on overlay click (outside dialog)
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) close(false);
            });
            
            // Close on Escape key
            const handleEscape = (e) => {
                if (e.key === 'Escape') {
                    document.removeEventListener('keydown', handleEscape);
                    close(false);
                }
            };
            document.addEventListener('keydown', handleEscape);
            
            confirmBtn.focus();
        });
    },
    
    confirm(message, title = 'Confirm') {
        return this.show({
            title,
            message,
            icon: '❓',
            type: 'warning'
        });
    },
    
    warning(message, title = 'Warning') {
        return this.show({
            title,
            message,
            icon: '⚠️',
            type: 'warning'
        });
    },
    
    danger(message, title = 'Are you sure?') {
        return this.show({
            title,
            message,
            icon: '🛑',
            type: 'danger',
            confirmText: 'Yes, I\'m sure'
        });
    }
};

// ============================================================================
// State
// ============================================================================

const state = {
    sessionId: null,
    ws: null,
    isRecording: false,
    mediaRecorder: null,
    audioChunks: [],
    recognition: null,
    currentTranscript: '',
    questionNumber: 0,
    totalQuestions: 10,
    startTime: null,
    durationInterval: null,
};

// ============================================================================
// DOM Elements
// ============================================================================

const elements = {
    questionText: document.getElementById('question-text'),
    aiAvatar: document.getElementById('ai-avatar'),
    webcam: document.getElementById('webcam'),
    webcamPlaceholder: document.getElementById('webcam-placeholder'),
    recordingIndicator: document.getElementById('recording-indicator'),
    transcriptText: document.getElementById('transcript-text'),
    micBtn: document.getElementById('mic-btn'),
    micBtnText: document.getElementById('mic-btn-text'),
    skipBtn: document.getElementById('skip-btn'),
    endBtn: document.getElementById('end-btn'),
    progressFill: document.getElementById('progress-fill'),
    progressText: document.getElementById('progress-text'),
    duration: document.getElementById('duration'),
    questionsAnswered: document.getElementById('questions-answered'),
    difficulty: document.getElementById('difficulty'),
    questionAudio: document.getElementById('question-audio'),
    // Loading overlay
    loadingOverlay: document.getElementById('loading-overlay'),
    loadingText: document.getElementById('loading-text'),
    loadingSubtext: document.getElementById('loading-subtext'),
};

// ============================================================================
// Loading Overlay Functions
// ============================================================================

function showLoading(text = 'Processing', subtext = '') {
    if (elements.loadingOverlay) {
        elements.loadingOverlay.classList.add('active');
        if (elements.loadingText) {
            elements.loadingText.innerHTML = text + '<span class="loading-dots"></span>';
        }
        if (elements.loadingSubtext) {
            elements.loadingSubtext.textContent = subtext;
        }
    }
    // Disable buttons
    if (elements.micBtn) elements.micBtn.disabled = true;
    if (elements.skipBtn) elements.skipBtn.disabled = true;
}

function hideLoading() {
    if (elements.loadingOverlay) {
        elements.loadingOverlay.classList.remove('active');
    }
    // Re-enable buttons
    if (elements.micBtn) elements.micBtn.disabled = false;
    if (elements.skipBtn) elements.skipBtn.disabled = false;
}

// ============================================================================
// Initialization
// ============================================================================

async function init() {
    // Get session ID from URL
    const pathParts = window.location.pathname.split('/');
    state.sessionId = pathParts[pathParts.length - 1];
    
    if (!state.sessionId) {
        Toast.error('No interview session found. Please start from the setup page.');
        setTimeout(() => { window.location.href = '/'; }, 2000);
        return;
    }
    
    // Initialize components
    await initWebcam();
    initSpeechRecognition();
    initWebSocket();
    startDurationTimer();
    
    // Set up event listeners
    elements.micBtn.addEventListener('click', toggleRecording);
    elements.skipBtn.addEventListener('click', skipQuestion);
    elements.endBtn.addEventListener('click', endInterview);
}

// ============================================================================
// WebSocket
// ============================================================================

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/interview/ws/${state.sessionId}`;
    
    state.ws = new WebSocket(wsUrl);
    
    state.ws.onopen = () => {
        console.log('WebSocket connected');
        // Start the interview
        state.ws.send(JSON.stringify({ type: 'start' }));
    };
    
    state.ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
    };
    
    state.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        showError('Connection error. Please refresh the page.');
    };
    
    state.ws.onclose = () => {
        console.log('WebSocket closed');
    };
}

function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'question':
            handleQuestion(message.data);
            break;
        case 'complete':
            handleComplete(message.data);
            break;
        case 'error':
            showError(message.message);
            break;
        case 'pong':
            // Heartbeat response
            break;
        default:
            console.log('Unknown message type:', message.type);
    }
}

function handleQuestion(data) {
    // Hide loading overlay - question arrived!
    hideLoading();
    
    // Only update question number for core questions, not follow-ups
    const isFollowup = data.action === 'followup' || data.followup_reason;
    
    if (!isFollowup && data.question_number) {
        state.questionNumber = data.question_number;
    } else if (!isFollowup && !data.question_number) {
        // Fallback: only increment for non-followup questions
        state.questionNumber = state.questionNumber + 1;
    }
    // For follow-ups, keep the same question number
    
    state.totalQuestions = data.total_questions || state.totalQuestions;
    
    // Update UI
    elements.questionText.textContent = data.question_text;
    elements.questionsAnswered.textContent = state.questionNumber;
    elements.difficulty.textContent = `${data.difficulty || 5}/10`;
    
    // Update progress - only based on core questions
    const progress = (state.questionNumber / state.totalQuestions) * 100;
    elements.progressFill.style.width = `${Math.min(progress, 100)}%`;
    
    // Show different text for follow-ups
    if (isFollowup) {
        elements.progressText.textContent = `Question ${state.questionNumber} of ${state.totalQuestions} (Follow-up)`;
    } else {
        elements.progressText.textContent = `Question ${state.questionNumber} of ${state.totalQuestions}`;
    }
    
    // Reset transcript
    elements.transcriptText.textContent = 'Click "Start Recording" when ready to answer...';
    state.currentTranscript = '';
    
    // Play audio if available
    if (data.audio_data?.audio_data) {
        playAudio(data.audio_data);
    }
    
    // Set avatar speaking state
    setAvatarSpeaking(true);
    setTimeout(() => setAvatarSpeaking(false), 3000);
}

function handleComplete(data) {
    stopDurationTimer();
    
    // Redirect to report
    window.location.href = `/report/${state.sessionId}`;
}

// ============================================================================
// Webcam
// ============================================================================

async function initWebcam() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: true,
        });
        
        elements.webcam.srcObject = stream;
        elements.webcamPlaceholder.style.display = 'none';
        
        // Store audio track for recording
        state.audioStream = stream;
        
    } catch (error) {
        console.error('Webcam error:', error);
        elements.webcamPlaceholder.textContent = 'Camera access denied';
    }
}

// ============================================================================
// Audio Recording & Speech Recognition
// ============================================================================

function initSpeechRecognition() {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        state.recognition = new SpeechRecognition();
        
        state.recognition.continuous = true;
        state.recognition.interimResults = true;
        state.recognition.lang = 'en-US';
        
        state.recognition.onresult = (event) => {
            let transcript = '';
            for (let i = 0; i < event.results.length; i++) {
                transcript += event.results[i][0].transcript;
            }
            state.currentTranscript = transcript;
            elements.transcriptText.textContent = transcript || 'Listening...';
        };
        
        state.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            if (event.error === 'no-speech') {
                elements.transcriptText.textContent = 'No speech detected. Try again.';
            }
        };
        
        state.recognition.onend = () => {
            if (state.isRecording) {
                // Restart if still recording
                state.recognition.start();
            }
        };
    } else {
        console.warn('Speech recognition not supported');
    }
}

function toggleRecording() {
    if (state.isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
}

function startRecording() {
    state.isRecording = true;
    elements.micBtn.classList.add('recording');
    elements.micBtnText.textContent = 'Stop Recording';
    elements.recordingIndicator.style.display = 'flex';
    elements.transcriptText.textContent = 'Listening...';
    
    // Start speech recognition
    if (state.recognition) {
        state.recognition.start();
    }
    
    // Start audio recording for backup
    if (state.audioStream) {
        const audioTrack = state.audioStream.getAudioTracks()[0];
        const audioStream = new MediaStream([audioTrack]);
        
        state.mediaRecorder = new MediaRecorder(audioStream);
        state.audioChunks = [];
        
        state.mediaRecorder.ondataavailable = (event) => {
            state.audioChunks.push(event.data);
        };
        
        state.mediaRecorder.start();
    }
}

function stopRecording() {
    state.isRecording = false;
    elements.micBtn.classList.remove('recording');
    elements.micBtnText.textContent = 'Start Recording';
    elements.recordingIndicator.style.display = 'none';
    
    // Stop speech recognition
    if (state.recognition) {
        state.recognition.stop();
    }
    
    // Stop media recorder
    if (state.mediaRecorder && state.mediaRecorder.state === 'recording') {
        state.mediaRecorder.stop();
    }
    
    // Submit the response
    if (state.currentTranscript.trim()) {
        submitResponse(state.currentTranscript);
    } else {
        elements.transcriptText.textContent = 'No response recorded. Try again or skip.';
    }
}

function submitResponse(transcript, skipLoadingMessage = false) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        // Show loading overlay while processing (unless already showing a custom message)
        if (!skipLoadingMessage) {
            showLoading('Evaluating your response', 'AI is analyzing your answer...');
        }
        
        state.ws.send(JSON.stringify({
            type: 'transcript',
            transcript: transcript,
        }));
        
        elements.transcriptText.textContent = 'Processing your response...';
    }
}

// ============================================================================
// Audio Playback
// ============================================================================

function playAudio(audioData) {
    if (!audioData.audio_data) return;
    
    try {
        const format = audioData.format || 'wav';
        const audioBlob = base64ToBlob(audioData.audio_data, `audio/${format}`);
        const audioUrl = URL.createObjectURL(audioBlob);
        
        elements.questionAudio.src = audioUrl;
        elements.questionAudio.play();
        
        elements.questionAudio.onended = () => {
            URL.revokeObjectURL(audioUrl);
            setAvatarSpeaking(false);
        };
        
    } catch (error) {
        console.error('Audio playback error:', error);
    }
}

function stopAudio() {
    if (elements.questionAudio) {
        elements.questionAudio.pause();
        elements.questionAudio.currentTime = 0;
        setAvatarSpeaking(false);
    }
}

function base64ToBlob(base64, type) {
    const byteCharacters = atob(base64);
    const byteNumbers = new Array(byteCharacters.length);
    
    for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray], { type });
}

// ============================================================================
// Avatar
// ============================================================================

function setAvatarSpeaking(speaking) {
    if (speaking) {
        elements.aiAvatar.classList.add('speaking');
    } else {
        elements.aiAvatar.classList.remove('speaking');
    }
}

// ============================================================================
// Controls
// ============================================================================

async function skipQuestion() {
    const confirmed = await Modal.warning(
        'This question will be marked as unanswered and you won\'t be able to return to it.',
        'Skip Question?'
    );
    
    if (confirmed) {
        // Stop any playing audio immediately
        stopAudio();
        
        // Show loading overlay with skip message
        showLoading('Skipping question', 'Moving to the next question...');
        submitResponse('[Question skipped by candidate]', true); // Skip loading message override
        Toast.info('Question skipped');
    }
}

async function endInterview() {
    const confirmed = await Modal.danger(
        'The interview will end and you\'ll receive your performance report. This cannot be undone.',
        'End Interview?'
    );
    
    if (confirmed) {
        // Show loading overlay
        showLoading('Generating your report', 'Analyzing interview performance...');
        Toast.info('Ending interview...');
        
        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send(JSON.stringify({ type: 'end' }));
        }
        
        // Also call REST endpoint as backup
        fetch(`/api/interview/${state.sessionId}/end`, { method: 'POST' })
            .then(() => {
                window.location.href = `/report/${state.sessionId}`;
            })
            .catch(() => {
                window.location.href = `/report/${state.sessionId}`;
            });
    }
}

// ============================================================================
// Timer
// ============================================================================

function startDurationTimer() {
    state.startTime = Date.now();
    
    state.durationInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - state.startTime) / 1000);
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;
        elements.duration.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }, 1000);
}

function stopDurationTimer() {
    if (state.durationInterval) {
        clearInterval(state.durationInterval);
    }
}

// ============================================================================
// Utilities
// ============================================================================

function showError(message) {
    Toast.error(message);
}

function showSuccess(message) {
    Toast.success(message);
}

function showInfo(message) {
    Toast.info(message);
}

// ============================================================================
// Start
// ============================================================================

document.addEventListener('DOMContentLoaded', init);

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (state.ws) {
        state.ws.close();
    }
    stopDurationTimer();
});
