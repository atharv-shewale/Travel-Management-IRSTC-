document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatWindow = document.getElementById('chat-window');
    const typingIndicator = document.getElementById('typing-indicator');

    // Retrieve or generate session ID
    let sessionId = localStorage.getItem('yatra_session_id');
    if (!sessionId) {
        sessionId = 'session_' + Math.random().toString(36).substring(2, 15);
        localStorage.setItem('yatra_session_id', sessionId);
    }

    // Scroll to bottom helper
    const scrollToBottom = () => {
        chatWindow.scrollTop = chatWindow.scrollHeight;
    };

    // Add message to UI
    const addMessage = (text, isUser = false) => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${isUser ? 'user-message' : 'ai-message'}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.textContent = isUser ? '👤' : '🤖';

        const content = document.createElement('div');
        content.className = 'content';
        content.textContent = text;

        msgDiv.appendChild(avatar);
        msgDiv.appendChild(content);
        
        chatWindow.appendChild(msgDiv);
        scrollToBottom();
    };

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const message = userInput.value.trim();
        if (!message) return;

        // Add user msg
        addMessage(message, true);
        userInput.value = '';
        
        // Show loading
        typingIndicator.classList.remove('hidden');
        scrollToBottom();

        try {
            const response = await fetch('http://localhost:8000/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    message: message
                })
            });

            const data = await response.json();
            
            typingIndicator.classList.add('hidden');
            addMessage(data.reply, false);

        } catch (error) {
            console.error('Error:', error);
            typingIndicator.classList.add('hidden');
            addMessage('Sorry, I am having trouble connecting to the server. Please ensure the backend is running.', false);
        }
    });
});
