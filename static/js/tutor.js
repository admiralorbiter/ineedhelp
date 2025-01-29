document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    const codeBtn = document.getElementById('code-btn');
    const fileBtn = document.getElementById('file-btn');
    const fileInput = document.getElementById('file-input');
    const filePreview = document.getElementById('file-preview');
    let currentConversationId = null;

    // Auto-resize input
    chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

    // Code button handler
    codeBtn.addEventListener('click', function() {
        // Toggle active state
        this.classList.toggle('active');
        
        // If button is active, insert code template
        if (this.classList.contains('active')) {
            const template = `What's your question?

\`\`\`python
Paste your code here
\`\`\``;
            chatInput.value = template;
        }
        
        // Adjust textarea height
        chatInput.style.height = 'auto';
        chatInput.style.height = chatInput.scrollHeight + 'px';
        chatInput.focus();
    });
    
    // Handle tab key in textarea for code indentation
    chatInput.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            e.preventDefault();
            const start = this.selectionStart;
            const end = this.selectionEnd;
            
            this.value = this.value.substring(0, start) + '    ' + this.value.substring(end);
            this.selectionStart = this.selectionEnd = start + 4;
        }
    });

    // Handle form submission
    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const message = chatInput.value.trim();
        const file = fileInput.files[0];
        
        if (!message && !file) return;
        
        const formData = new FormData();
        formData.append('message', message);
        if (file) {
            formData.append('file', file);
        }
        if (currentConversationId) {
            formData.append('conversation_id', currentConversationId);
        }
        
        try {
            const response = await fetch('/tutor/send_message', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to send message');
            }

            if (data.success) {
                // Reset the form
                chatInput.value = '';
                chatInput.style.height = 'auto';  // Reset height
                fileInput.value = '';  // Clear file input
                filePreview.textContent = '';  // Clear file preview
                filePreview.classList.remove('active');  // Hide preview container
                
                // Reset any active states
                codeBtn.classList.remove('active');
                
                currentConversationId = data.conversation_id;
                appendMessages(data.messages);
            }
        } catch (error) {
            console.error('Error:', error);
            // Create and show an error message to the user
            const errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger';
            errorDiv.textContent = error.message;
            chatMessages.appendChild(errorDiv);
            
            // Don't reset the form on error so user can try again
            chatInput.value = message;
        }
    });

    // Handle chat history clicks
    document.querySelectorAll('.history-item').forEach(item => {
        item.addEventListener('click', async function() {
            const conversationId = this.dataset.conversationId;
            try {
                const response = await fetch(`/tutor/get_conversation/${conversationId}`);
                const data = await response.json();
                currentConversationId = conversationId;
                chatMessages.innerHTML = '';
                appendMessages(data.messages);
            } catch (error) {
                console.error('Error:', error);
                alert('Failed to load conversation. Please try again.');
            }
        });
    });

    // Add new chat button handler
    document.getElementById('new-chat-btn').addEventListener('click', function() {
        currentConversationId = null;
        chatMessages.innerHTML = '';
        chatInput.value = '';
    });

    fileBtn.addEventListener('click', function() {
        fileInput.click();
    });

    fileInput.addEventListener('change', function() {
        const file = this.files[0];
        if (file) {
            filePreview.textContent = `Selected file: ${file.name}`;
            filePreview.classList.add('active');
        } else {
            filePreview.textContent = '';
            filePreview.classList.remove('active');
        }
    });

    function appendMessages(messages) {
        messages.forEach(message => {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${message.role}`;
            
            // Add model indicator for assistant messages
            let modelIndicator = '';
            if (message.role === 'assistant') {
                const modelName = message.model || 'GPT-3.5';
                modelIndicator = `<div class="model-indicator">${modelName}</div>`;
            }
            
            // Process content for code blocks and file attachments
            let content = message.content;
            
            // Handle file attachments
            const fileMatch = content.match(/\[Attached file: (.*?)\]/);
            if (fileMatch) {
                const filename = fileMatch[1];
                const fileExt = filename.split('.').pop().toLowerCase();
                
                // Create file attachment display
                const isImage = ['jpg', 'jpeg', 'png', 'gif'].includes(fileExt);
                const attachmentHtml = isImage 
                    ? `<div class="file-attachment">
                        <img src="/tutor/uploads/${filename}" alt="Uploaded image" class="uploaded-image">
                       </div>`
                    : `<div class="file-attachment">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"/>
                        </svg>
                        <a href="/tutor/uploads/${filename}" target="_blank">${filename}</a>
                       </div>`;
                       
                content = content.replace(fileMatch[0], '') + attachmentHtml;
            }
            
            // Replace markdown code blocks with highlighted HTML
            content = content.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
                const language = lang || 'plaintext';
                const highlighted = hljs.highlight(code.trim(), {
                    language: language,
                    ignoreIllegals: true
                }).value;
                return `<pre><code class="hljs language-${language}">${highlighted}</code></pre>`;
            });
            
            // Replace inline code for both message types
            content = content.replace(/`([^`]+)`/g, '<code>$1</code>');
            
            let feedbackHtml = '';
            if (message.role === 'assistant') {
                feedbackHtml = `
                    <div class="feedback-buttons">
                        <button class="btn btn-sm btn-outline-success feedback-btn" data-feedback="understood">
                            I understand ✓
                        </button>
                        <button class="btn btn-sm btn-outline-danger feedback-btn" data-feedback="confused">
                            Still confused ?
                        </button>
                    </div>
                `;
            }
            
            messageDiv.innerHTML = `
                ${modelIndicator}
                <div class="message-content">
                    ${content}
                </div>
                ${feedbackHtml}
            `;
            chatMessages.appendChild(messageDiv);
        });
        
        // Scroll to bottom and initialize syntax highlighting
        chatMessages.scrollTop = chatMessages.scrollHeight;
        document.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightBlock(block);
        });
        
        // Add feedback button handlers
        document.querySelectorAll('.feedback-btn').forEach(button => {
            button.addEventListener('click', async function() {
                const messageId = this.closest('.feedback-buttons').dataset.messageId;
                const feedback = this.dataset.feedback;
                const understood = feedback === 'understood';
                
                try {
                    const response = await fetch('/tutor/interaction_feedback', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            message_id: messageId,
                            was_helpful: true,
                            understood_concept: understood,
                            topic: detectTopic(this.closest('.message').querySelector('.message-content').textContent)
                        })
                    });
                    
                    if (!response.ok) throw new Error('Failed to send feedback');
                    
                    // Disable feedback buttons after selection
                    this.closest('.feedback-buttons').querySelectorAll('button').forEach(btn => {
                        btn.disabled = true;
                    });
                    this.classList.add('selected');
                    
                } catch (error) {
                    console.error('Error sending feedback:', error);
                }
            });
        });
    }

    function detectTopic(content) {
        // Simple topic detection based on keywords
        const topics = {
            'loop': 'loops',
            'function': 'functions',
            'class': 'classes',
            'variable': 'variables',
            'list': 'data_structures',
            'dictionary': 'data_structures',
            'if': 'control_flow',
            'else': 'control_flow'
        };
        
        for (const [keyword, topic] of Object.entries(topics)) {
            if (content.toLowerCase().includes(keyword)) {
                return topic;
            }
        }
        return 'general';
    }
}); 