/**
 * DataReady.io - Report Page JavaScript
 * 
 * Handles:
 * - Report data fetching
 * - Score animations
 * - Dynamic content rendering
 */

// ============================================================================
// State
// ============================================================================

let sessionId = null;

// ============================================================================
// DOM Elements
// ============================================================================

const elements = {
    loading: document.getElementById('loading'),
    reportContent: document.getElementById('report-content'),
    reportRole: document.getElementById('report-role'),
    reportDuration: document.getElementById('report-duration'),
    reportDate: document.getElementById('report-date'),
    scoreNumber: document.getElementById('score-number'),
    scoreCircle: document.getElementById('score-circle'),
    verdictValue: document.getElementById('verdict-value'),
    strengthsList: document.getElementById('strengths-list'),
    improvementsList: document.getElementById('improvements-list'),
    communicationFeedback: document.getElementById('communication-feedback'),
    roadmapWeeks: document.getElementById('roadmap-weeks'),
    // New elements
    statTotal: document.getElementById('stat-total'),
    statAnswered: document.getElementById('stat-answered'),
    statSkipped: document.getElementById('stat-skipped'),
    statFollowups: document.getElementById('stat-followups'),
    questionsList: document.getElementById('questions-list'),
};

// ============================================================================
// Initialization
// ============================================================================

async function init() {
    // Get session ID from URL
    const pathParts = window.location.pathname.split('/');
    sessionId = pathParts[pathParts.length - 1];
    
    if (!sessionId) {
        showError('No interview session found.');
        return;
    }
    
    // Set current date
    elements.reportDate.textContent = new Date().toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
    });
    
    // Fetch report
    await fetchReport();
}

// ============================================================================
// Data Fetching
// ============================================================================

async function fetchReport() {
    try {
        const response = await fetch(`/api/report/${sessionId}`);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to load report');
        }
        
        const report = await response.json();
        renderReport(report);
        
    } catch (error) {
        console.error('Report fetch error:', error);
        showError(error.message);
    }
}

// ============================================================================
// Rendering
// ============================================================================

function renderReport(report) {
    // Hide loading, show content
    elements.loading.style.display = 'none';
    elements.reportContent.style.display = 'block';
    
    // Header info
    const roleNames = {
        'junior_data_engineer': 'Junior Data Engineer',
        'mid_data_engineer': 'Mid-Level Data Engineer',
        'senior_data_engineer': 'Senior Data Engineer',
        'staff_data_engineer': 'Staff Data Engineer',
        'principal_data_engineer': 'Principal Data Engineer',
    };
    elements.reportRole.textContent = roleNames[report.target_role] || report.target_role;
    elements.reportDuration.textContent = Math.round(report.interview_duration_minutes);
    
    // Interview stats
    renderInterviewStats(report);
    
    // Animate overall score
    animateScore(report.overall_score);
    
    // Hiring verdict with SVG icons
    const verdictConfig = {
        'strong_hire': {
            icon: `<svg class="verdict-icon verdict-strong-hire" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
            </svg>`,
            text: 'Strong Hire',
            class: 'verdict-strong-hire'
        },
        'hire': {
            icon: `<svg class="verdict-icon verdict-hire" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>`,
            text: 'Hire',
            class: 'verdict-hire'
        },
        'borderline': {
            icon: `<svg class="verdict-icon verdict-borderline" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>`,
            text: 'Borderline',
            class: 'verdict-borderline'
        },
        'needs_improvement': {
            icon: `<svg class="verdict-icon verdict-needs-improvement" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
                <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
            </svg>`,
            text: 'Needs Improvement',
            class: 'verdict-needs-improvement'
        },
    };
    const verdict = verdictConfig[report.hiring_verdict] || { icon: '', text: report.hiring_verdict, class: '' };
    elements.verdictValue.innerHTML = `${verdict.icon} ${verdict.text}`;
    elements.verdictValue.className = `verdict-value ${verdict.class}`;
    
    // Dimension scores
    renderDimensionScores(report.dimension_scores);
    
    // Strengths
    renderList(elements.strengthsList, report.top_strengths);
    
    // Improvements
    renderList(elements.improvementsList, report.areas_for_improvement);
    
    // Communication feedback
    elements.communicationFeedback.textContent = report.communication_feedback || 'No specific feedback available.';
    
    // Per-question feedback
    if (report.question_feedback && report.question_feedback.length > 0) {
        renderQuestionFeedback(report.question_feedback);
    } else {
        elements.questionsList.innerHTML = '<p class="loading-text">No detailed question feedback available</p>';
    }
    
    // Study roadmap
    if (report.study_roadmap) {
        renderRoadmap(report.study_roadmap);
    }
}

function renderInterviewStats(report) {
    // Calculate stats from question_feedback if available
    const questions = report.question_feedback || [];
    const totalQuestions = questions.length || report.total_questions || 0;
    const skippedQuestions = questions.filter(q => q.skipped).length;
    const answeredQuestions = totalQuestions - skippedQuestions;
    const followupQuestions = questions.filter(q => q.is_followup).length;
    
    // Animate stats
    animateNumber(elements.statTotal, totalQuestions);
    animateNumber(elements.statAnswered, answeredQuestions);
    animateNumber(elements.statSkipped, skippedQuestions);
    animateNumber(elements.statFollowups, followupQuestions);
}

function animateNumber(element, target) {
    const duration = 1000;
    const startTime = performance.now();
    
    function animate(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        
        element.textContent = Math.round(target * eased);
        
        if (progress < 1) {
            requestAnimationFrame(animate);
        }
    }
    
    requestAnimationFrame(animate);
}

function renderQuestionFeedback(questions) {
    const coreQuestions = questions.filter(q => !q.is_followup);
    
    const html = coreQuestions.map((q, index) => {
        const score = q.score || 0;
        const scorePercent = (score / 10) * 100;
        
        // Determine score class
        let scoreClass = '';
        if (q.skipped) {
            scoreClass = 'skipped';
        } else if (score >= 7) {
            scoreClass = 'correct';
        } else if (score >= 4) {
            scoreClass = 'partial';
        } else {
            scoreClass = 'incorrect';
        }
        
        // Build improvement tips HTML
        let improvementHtml = '';
        if (q.improvements && q.improvements.length > 0) {
            improvementHtml = `
                <div class="question-detail">
                    <div class="question-detail-label">Areas for Improvement</div>
                    <div class="question-detail-content improvement-tips">
                        <ul>
                            ${q.improvements.map(imp => `<li>${imp}</li>`).join('')}
                        </ul>
                    </div>
                </div>
            `;
        }
        
        // Build expected answer HTML (only show if score < 7)
        let expectedHtml = '';
        if (q.expected_answer && score < 7) {
            expectedHtml = `
                <div class="question-detail">
                    <div class="question-detail-label">Expected Answer</div>
                    <div class="question-detail-content expected-answer">
                        ${q.expected_answer}
                    </div>
                </div>
            `;
        }
        
        // Your answer (transcript)
        let yourAnswerHtml = '';
        if (q.transcript && !q.skipped) {
            yourAnswerHtml = `
                <div class="question-detail">
                    <div class="question-detail-label">Your Answer</div>
                    <div class="question-detail-content your-answer">
                        ${q.transcript}
                    </div>
                </div>
            `;
        } else if (q.skipped) {
            yourAnswerHtml = `
                <div class="question-detail">
                    <div class="question-detail-label">Your Answer</div>
                    <div class="question-detail-content your-answer" style="color: var(--color-text-muted); font-style: italic;">
                        Question was skipped
                    </div>
                </div>
            `;
        }
        
        // What went well
        let strengthsHtml = '';
        if (q.what_went_well && q.what_went_well.length > 0) {
            strengthsHtml = `
                <div class="question-detail">
                    <div class="question-detail-label">What Went Well</div>
                    <div class="question-detail-content" style="border-left: 3px solid var(--color-success);">
                        <ul style="list-style: none; padding: 0; margin: 0;">
                            ${q.what_went_well.map(item => `<li style="padding: 2px 0;">✓ ${item}</li>`).join('')}
                        </ul>
                    </div>
                </div>
            `;
        }
        
        // Tags
        const tags = [];
        if (q.skill_name) tags.push(q.skill_name);
        if (q.category) tags.push(q.category);
        if (q.difficulty) tags.push(q.difficulty);
        
        const tagsHtml = tags.length > 0 ? `
            <div class="question-tags">
                ${tags.map(t => `<span class="question-tag">${t}</span>`).join('')}
            </div>
        ` : '';
        
        return `
            <div class="question-card" data-index="${index}">
                <div class="question-header" onclick="toggleQuestion(${index})">
                    <div class="question-number ${scoreClass}">${index + 1}</div>
                    <div class="question-title">${q.question || 'Question'}</div>
                    <div class="question-score">
                        ${q.skipped ? 'Skipped' : `${score.toFixed(1)}/10`}
                        <div class="question-score-bar">
                            <div class="question-score-fill" style="width: ${scorePercent}%"></div>
                        </div>
                    </div>
                    <div class="question-toggle">▼</div>
                </div>
                <div class="question-body">
                    ${yourAnswerHtml}
                    ${strengthsHtml}
                    ${improvementHtml}
                    ${expectedHtml}
                    ${tagsHtml}
                </div>
            </div>
        `;
    }).join('');
    
    elements.questionsList.innerHTML = html || '<p class="loading-text">No question feedback available</p>';
}

function animateScore(score) {
    const duration = 1500;
    const startTime = performance.now();
    
    // Circle animation
    const circumference = 2 * Math.PI * 78; // radius = 78
    const targetOffset = circumference - (score / 100) * circumference;
    
    function animate(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Easing function
        const eased = 1 - Math.pow(1 - progress, 3);
        
        // Update number
        const currentScore = Math.round(score * eased);
        elements.scoreNumber.textContent = currentScore;
        
        // Update circle
        const currentOffset = circumference - (circumference - targetOffset) * eased;
        elements.scoreCircle.style.strokeDashoffset = currentOffset;
        
        if (progress < 1) {
            requestAnimationFrame(animate);
        }
    }
    
    requestAnimationFrame(animate);
}

function renderDimensionScores(scores) {
    const dimensions = {
        'Technical Correctness': 'dim-technical',
        'Depth of Understanding': 'dim-depth',
        'Practical Experience': 'dim-practical',
        'Communication Clarity': 'dim-communication',
        'Confidence': 'dim-confidence',
    };
    
    Object.entries(dimensions).forEach(([name, id]) => {
        const element = document.getElementById(id);
        if (!element) return;
        
        const score = scores[name] || 0;
        const valueEl = element.querySelector('.dimension-value');
        const fillEl = element.querySelector('.dimension-fill');
        
        valueEl.textContent = `${score.toFixed(1)}/10`;
        
        // Animate fill
        setTimeout(() => {
            fillEl.style.width = `${score * 10}%`;
        }, 300);
    });
}

function renderList(element, items) {
    if (!items || items.length === 0) {
        element.innerHTML = '<li>No specific items noted</li>';
        return;
    }
    
    element.innerHTML = items.map(item => `<li>${item}</li>`).join('');
}

function renderRoadmap(roadmap) {
    if (!roadmap.weeks || roadmap.weeks.length === 0) {
        elements.roadmapWeeks.innerHTML = '<p class="loading-text">No roadmap available</p>';
        return;
    }
    
    const weeksHtml = roadmap.weeks.map(week => `
        <div class="week-card">
            <div class="week-number">${week.week}</div>
            <div class="week-content">
                <h4>${week.focus}</h4>
                <ul class="week-activities">
                    ${week.activities.map(a => `<li>• ${a}</li>`).join('')}
                </ul>
            </div>
        </div>
    `).join('');
    
    elements.roadmapWeeks.innerHTML = weeksHtml;
}

// ============================================================================
// Question Toggle
// ============================================================================

function toggleQuestion(index) {
    const card = document.querySelector(`.question-card[data-index="${index}"]`);
    if (card) {
        card.classList.toggle('expanded');
    }
}

// Expand all questions for printing
function expandAllQuestions() {
    document.querySelectorAll('.question-card').forEach(card => {
        card.classList.add('expanded');
    });
}

// Collapse all questions
function collapseAllQuestions() {
    document.querySelectorAll('.question-card').forEach(card => {
        card.classList.remove('expanded');
    });
}

// ============================================================================
// Print Handler
// ============================================================================

function handlePrint() {
    // Expand all questions before printing
    expandAllQuestions();
    
    // Wait for DOM update
    setTimeout(() => {
        window.print();
    }, 100);
}

// ============================================================================
// Utilities
// ============================================================================

function showError(message) {
    elements.loading.innerHTML = `
        <div style="text-align: center;">
            <h2 style="color: var(--color-error); margin-bottom: var(--space-md);">Error Loading Report</h2>
            <p style="color: var(--color-text-secondary); margin-bottom: var(--space-lg);">${message}</p>
            <button class="btn-primary" onclick="window.location.href='/'">
                Return Home
            </button>
        </div>
    `;
}

// ============================================================================
// Start
// ============================================================================

document.addEventListener('DOMContentLoaded', init);
