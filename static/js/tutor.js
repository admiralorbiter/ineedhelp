document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    let currentConversationId = null;

    // Auto-resize input
    chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

    // Handle form submission
    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const message = chatInput.value.trim();
        if (!message) return;

        // Clear input
        chatInput.value = '';
        chatInput.style.height = 'auto';

        try {
            const response = await fetch('/tutor/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    conversation_id: currentConversationId
                })
            });

            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to send message');
            }

            if (data.success) {
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
            
            // Restore the message in the input
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

    function appendMessages(messages) {
        messages.forEach(message => {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${message.role}`;
            messageDiv.innerHTML = `
                <div class="message-content">
                    ${message.content}
                </div>
            `;
            chatMessages.appendChild(messageDiv);
        });
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}); 