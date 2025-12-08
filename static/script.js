// WebSocket connection
let ws = null;
let isGenerating = false;

// DOM Elements
const generateBtn = document.getElementById('generate-btn');
const topicInput = document.getElementById('topic');
const rssFeedInput = document.getElementById('rss-feed');
const blogOutput = document.getElementById('blog-output');
const copyBtn = document.getElementById('copy-btn');
const messagesDiv = document.getElementById('messages');
const messagesSection = document.querySelector('.messages-section');
const similaritySection = document.querySelector('.similarity-section');
const metadataSection = document.getElementById('metadata');

// Pipeline steps
const pipelineSteps = {
    outline: document.querySelector('[data-stage="outline"]'),
    writer: document.querySelector('[data-stage="writer"]'),
    style: document.querySelector('[data-stage="style"]'),
    editor: document.querySelector('[data-stage="editor"]')
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    generateBtn.addEventListener('click', startGeneration);
    copyBtn.addEventListener('click', copyToClipboard);
    
    // Allow Enter to submit (with Shift+Enter for new line)
    topicInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            startGeneration();
        }
    });
});

function startGeneration() {
    const topic = topicInput.value.trim();
    const rssFeed = rssFeedInput.value.trim();
    
    if (!topic) {
        alert('Please enter a blog topic');
        return;
    }
    
    if (!rssFeed) {
        alert('Please enter an RSS feed URL');
        return;
    }
    
    if (isGenerating) {
        return;
    }
    
    resetUI();
    
    // Update button state
    isGenerating = true;
    generateBtn.disabled = true;
    generateBtn.querySelector('.btn-text').textContent = 'Generating...';
    generateBtn.querySelector('.btn-loader').style.display = 'inline-block';
    
    // Show messages section
    messagesSection.style.display = 'block';
    
    // Connect WebSocket
    connectWebSocket(topic, rssFeed);
}

function connectWebSocket(topic, rssFeed) {
    const protocol = window.location.protocol === "https:" ? "wss://" : "ws://";
    const wsUrl = `${protocol}${window.location.host}/ws/generate`;
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        ws.send(JSON.stringify({ topic, rss_feed: rssFeed }));
        addMessage('Connected to server...', 'info');
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleMessage(data);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        addMessage('Connection error occurred', 'error');
        resetGenerationState();
    };
    
    ws.onclose = () => {
        console.log('WebSocket closed');
        if (isGenerating) {
            resetGenerationState();
        }
    };
}

function handleMessage(data) {
    console.log('Received:', data);
    
    switch (data.type) {
        case 'status':
            updatePipelineStatus(data.stage, data.message);
            addMessage(data.message, 'info');
            break;
            
        case 'progress':
            addMessage(`Draft: ${data.word_count} words`, 'info');
            break;
            
        case 'similarity':
            updateSimilarityScores(data);
            break;
            
        case 'complete':
            handleCompletion(data);
            break;
            
        case 'error':
            addMessage(data.message, 'error');
            resetGenerationState();
            break;
    }
}

function updatePipelineStatus(stage, message) {
    // Reset all steps
    Object.values(pipelineSteps).forEach(step => {
        step.classList.remove('active');
    });
    
    // Mark current and completed steps
    let foundCurrent = false;
    for (const [key, step] of Object.entries(pipelineSteps)) {
        if (key === stage) {
            step.classList.add('active');
            step.classList.remove('completed');
            step.querySelector('.step-status').textContent = 'In Progress';
            
            // Animate progress bar
            const progressBar = step.querySelector('.progress-bar');
            if (progressBar) {
                progressBar.style.width = '0%';
                setTimeout(() => {
                    progressBar.style.width = '70%';
                }, 100);
            }
            
            foundCurrent = true;
        } else if (!foundCurrent) {
            step.classList.add('completed');
            step.classList.remove('active');
            step.querySelector('.step-status').textContent = 'Completed';
            
            // Full progress for completed
            const progressBar = step.querySelector('.progress-bar');
            if (progressBar) {
                progressBar.style.width = '100%';
            }
        } else {
            step.classList.remove('active', 'completed');
            step.querySelector('.step-status').textContent = 'Waiting';
            
            // Reset progress for waiting
            const progressBar = step.querySelector('.progress-bar');
            if (progressBar) {
                progressBar.style.width = '0%';
            }
        }
    }
}

function updateSimilarityScores(data) {
    similaritySection.style.display = 'block';
    
    const combined = data.combined_similarity;
    const embedding = data.embedding_similarity;
    const llm = data.llm_similarity;
    
    // Update values
    document.getElementById('combined-similarity').textContent = 
        combined ? combined.toFixed(4) : '--';
    // document.getElementById('embedding-similarity').textContent = 
    //     embedding ? embedding.toFixed(4) : '--';
    // document.getElementById('llm-similarity').textContent = 
    //     llm ? llm.toFixed(4) : '--';
    document.getElementById('author-name').textContent = 
        data.author || 'Unknown';
    document.getElementById('rewrite-attempts').textContent = 
        data.rewrite_attempts || 0;
    
    // Animate progress bars
    setTimeout(() => {
        if (combined) {
            document.getElementById('combined-fill').style.width = `${combined * 100}%`;
        }
        if (embedding) {
            document.getElementById('embedding-fill').style.width = `${embedding * 100}%`;
        }
        if (llm) {
            document.getElementById('llm-fill').style.width = `${llm * 100}%`;
        }
    }, 100);
}

function handleCompletion(data) {
    // Mark all steps as completed
    Object.values(pipelineSteps).forEach(step => {
        step.classList.add('completed');
        step.classList.remove('active');
        step.querySelector('.step-status').textContent = 'Completed';
    
        const progressBar = step.querySelector('.progress-bar');
        if (progressBar) {
            progressBar.style.width = '100%';
        }
    });
    
    // Display blog
    displayBlog(data.blog);
    
    // Update metadata
    if (data.metadata) {
        metadataSection.style.display = 'block';
        document.getElementById('word-count').textContent = 
            data.metadata.word_count || '--';
        document.getElementById('validated').textContent = 
            data.metadata.validated ? '✓ Yes' : '✗ No';
    }
    
    // Show copy button
    copyBtn.style.display = 'block';
    
    addMessage('✓ Blog generation complete!', 'success');
    
    // Reset generation state
    resetGenerationState();
}

function displayBlog(content) {
    // Remove placeholder
    blogOutput.innerHTML = '';
    
    // Parse and display markdown-like content
    const lines = content.split('\n');
    let html = '';
    let inCodeBlock = false;
    let codeContent = '';
    
    for (let line of lines) {
        // Code blocks
        if (line.trim().startsWith('```')) {
            if (inCodeBlock) {
                html += `<pre><code>${escapeHtml(codeContent)}</code></pre>`;
                codeContent = '';
                inCodeBlock = false;
            } else {
                inCodeBlock = true;
            }
            continue;
        }
        
        if (inCodeBlock) {
            codeContent += line + '\n';
            continue;
        }
        
        // Headers
        if (line.startsWith('# ')) {
            html += `<h1>${escapeHtml(line.substring(2))}</h1>`;
        } else if (line.startsWith('## ')) {
            html += `<h2>${escapeHtml(line.substring(3))}</h2>`;
        } else if (line.startsWith('### ')) {
            html += `<h3>${escapeHtml(line.substring(4))}</h3>`;
        } else if (line.trim() === '') {
            // Empty line - paragraph break
        } else {
            // Regular paragraph
            html += `<p>${formatInlineMarkdown(escapeHtml(line))}</p>`;
        }
    }
    
    blogOutput.innerHTML = html;
}

function formatInlineMarkdown(text) {
    // Bold
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Italic
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // Inline code
    text = text.replace(/`(.*?)`/g, '<code>$1</code>');
    return text;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function addMessage(message, type = 'info') {
    const messageEl = document.createElement('div');
    messageEl.className = `message ${type}`;
    messageEl.textContent = message;
    messagesDiv.appendChild(messageEl);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function resetUI() {
    // Clear blog output
    blogOutput.innerHTML = `
        <div class="placeholder">
            <div class="placeholder-icon">⏳</div>
            <p>Generating your blog...</p>
        </div>
    `;
    
    // Hide sections
    copyBtn.style.display = 'none';
    metadataSection.style.display = 'none';
    similaritySection.style.display = 'none';
    
    // Clear messages
    messagesDiv.innerHTML = '';
    
    // Reset pipeline
    Object.values(pipelineSteps).forEach(step => {
        step.classList.remove('active', 'completed');
        step.querySelector('.step-status').textContent = 'Waiting';
        
        // Reset progress bars
        const progressBar = step.querySelector('.progress-bar');
        if (progressBar) {
            progressBar.style.width = '0%';
        }
    });
    
    // Reset similarity bars
    document.querySelectorAll('.metric-fill').forEach(fill => {
        fill.style.width = '0%';
    });
}

function resetGenerationState() {
    isGenerating = false;
    generateBtn.disabled = false;
    generateBtn.querySelector('.btn-text').textContent = 'Generate Blog';
    generateBtn.querySelector('.btn-loader').style.display = 'none';
    
    if (ws) {
        ws.close();
        ws = null;
    }
}

function copyToClipboard() {
    const text = blogOutput.innerText;
    
    navigator.clipboard.writeText(text).then(() => {
        const originalText = copyBtn.textContent;
        copyBtn.textContent = '✓ Copied!';
        copyBtn.style.background = '#4caf50';
        
        setTimeout(() => {
            copyBtn.textContent = originalText;
            copyBtn.style.background = '';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        alert('Failed to copy to clipboard');
    });
}