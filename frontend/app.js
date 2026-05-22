document.addEventListener('DOMContentLoaded', () => {
    // UI Selectors
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatWindow = document.getElementById('chat-window');
    const typingIndicator = document.getElementById('typing-indicator');
    
    // Sidebar & Session Selectors
    const sidebar = document.getElementById('sidebar');
    const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
    const dashboardContainer = document.querySelector('.dashboard-container');
    const newChatBtn = document.getElementById('new-chat-btn');
    const sessionsList = document.getElementById('sessions-list');
    const statsBookingsCount = document.getElementById('stats-bookings-count');

    // NEW: PNR Sidebar selectors
    const sidebarPnrInput = document.getElementById('sidebar-pnr-input');
    const sidebarPnrBtn = document.getElementById('sidebar-pnr-btn');

    // Modals
    const seatMapModal = document.getElementById('seat-map-modal');
    const ticketModal = document.getElementById('ticket-modal');
    const closeSeatMapBtn = document.getElementById('close-seat-map-btn');
    const closeTicketModalBtn = document.getElementById('close-ticket-modal-btn');
    const downloadTicketBtn = document.getElementById('download-ticket-btn');

    // UPI Payment Sandbox Modals
    const paymentModal = document.getElementById('payment-modal');
    const closePaymentBtn = document.getElementById('close-payment-btn');
    const payPassengerName = document.getElementById('pay-passenger-name');
    const payRouteInfo = document.getElementById('pay-route-info');
    const payAmountInfo = document.getElementById('pay-amount-info');
    const paySubmitBtn = document.getElementById('pay-submit-btn');

    // Accessibility Controls
    const micBtn = document.getElementById('mic-btn');
    const ttsToggleBtn = document.getElementById('tts-toggle-btn');

    // State Variables
    let sessionId = localStorage.getItem('yatra_session_id');
    let ttsEnabled = localStorage.getItem('yatra_tts_enabled') === 'true';
    let isListening = false;
    let recognition = null;
    let activeBookingData = null; // Store data for map and download
    let activeAudioGuideUtterance = null; // Voice guide pointer
    let isPaid = false; // State variable to track UPI payment completion

    // Set voice button initial state
    if (ttsEnabled) {
        ttsToggleBtn.classList.add('speech-active');
        ttsToggleBtn.querySelector('.btn-text').textContent = "Voice On";
    } else {
        ttsToggleBtn.classList.remove('speech-active');
        ttsToggleBtn.querySelector('.btn-text').textContent = "Voice Off";
    }

    // Initialize Sessions List and Stats
    const initPortal = async () => {
        if (!sessionId) {
            startNewSession();
        }
        await loadSessions();
        await updateBookingStats();
        updateTransitStepper(0); // Initialize Tracker at Step 0: Search
    };

    const startNewSession = () => {
        sessionId = 'session_' + Math.random().toString(36).substring(2, 15);
        localStorage.setItem('yatra_session_id', sessionId);
        
        // Reset Chat UI
        chatWindow.innerHTML = `
            <div class="message ai-message">
                <div class="avatar">
                    <img src="logo.png" alt="YatraAI avatar">
                </div>
                <div class="content-wrapper">
                    <div class="content">
                        Namaste! I am YatraAI, your elite train travel concierge. I am ready to arrange your next journey, check ticket availability, or track your live PNR status.
                        <br><br>
                        Where would you like to travel today? For instance, try asking:
                        <em>"Find trains from Delhi to Mumbai tomorrow"</em> or 
                        <em>"Show me sightseeing highlights for Jaipur"</em>.
                    </div>
                </div>
            </div>
        `;
        updateTransitStepper(0);
        loadSessions();
    };

    const loadSessions = async () => {
        try {
            const response = await fetch('http://localhost:8000/api/sessions');
            const result = await response.json();
            
            if (result.status === 'success' && result.data) {
                sessionsList.innerHTML = '';
                
                if (result.data.length === 0) {
                    sessionsList.innerHTML = `<div style="text-align: center; color: var(--text-muted); font-size: 0.8rem; padding: 10px;">No recent journeys</div>`;
                    return;
                }

                result.data.forEach(session => {
                    const item = document.createElement('div');
                    item.className = `session-item ${session.session_id === sessionId ? 'active' : ''}`;
                    item.innerHTML = `
                        <span class="session-icon">🚆</span>
                        <div class="session-details">
                            <span class="session-title-text" title="${session.title}">${session.title}</span>
                        </div>
                    `;
                    item.onclick = () => switchSession(session.session_id);
                    sessionsList.appendChild(item);
                });
            }
        } catch (e) {
            console.error("Failed to load sessions", e);
        }
    };

    const switchSession = async (sid) => {
        if (sid === sessionId) return;
        sessionId = sid;
        localStorage.setItem('yatra_session_id', sessionId);
        
        // Update active class in sidebar
        document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
        const activeItem = Array.from(document.querySelectorAll('.session-item')).find(item => item.textContent.includes(sid));
        if (activeItem) activeItem.classList.add('active');

        // Show typing indicator during load
        typingIndicator.classList.remove('hidden');
        
        try {
            const response = await fetch(`http://localhost:8000/api/sessions/${sid}/history`);
            const result = await response.json();
            
            typingIndicator.classList.add('hidden');
            chatWindow.innerHTML = '';

            if (result.status === 'success' && result.data && result.data.length > 0) {
                const historyToRender = result.data.filter(msg => msg.role !== 'system');
                
                historyToRender.forEach((msg, index) => {
                    let contentText = msg.content || "";
                    let parsedUiData = null;
                    const uiDataRegex = /```ui-data\s*([\s\S]*?)\s*```/;
                    const match = contentText.match(uiDataRegex);
                    if (match) {
                        try {
                            parsedUiData = JSON.parse(match[1]);
                        } catch (err) {
                            console.error(err);
                        }
                    }

                    if (msg.role === 'user') {
                        addMessage(contentText, true, null, false);
                    } else if (msg.role === 'assistant') {
                        addMessage(contentText, false, parsedUiData, false);
                    }
                });
                
                // Set stepper tracker logically based on last message type
                const lastMsg = historyToRender[historyToRender.length - 1];
                if (lastMsg && lastMsg.role === 'assistant') {
                    if (lastMsg.content.includes("booking_success") || lastMsg.content.includes("PNR")) {
                        updateTransitStepper(3); // Ticket
                    } else if (lastMsg.content.includes("trains") || lastMsg.content.includes("Fare")) {
                        updateTransitStepper(1); // Class selection
                    } else {
                        updateTransitStepper(0); // Search
                    }
                }
            } else {
                startNewSession();
            }
            scrollToBottom();
            loadSessions();
        } catch (error) {
            console.error("Error loading session history", error);
            typingIndicator.classList.add('hidden');
            addMessage("Unable to load history. Please ensure the backend is active.", false);
        }
    };

    const updateBookingStats = async () => {
        try {
            const response = await fetch('http://localhost:8000/api/bookings');
            const result = await response.json();
            if (result.status === 'success' && result.data) {
                statsBookingsCount.textContent = result.data.length;
            }
        } catch (e) {
            console.error("Failed to load booking stats", e);
        }
    };

    // NEW: PNR Sidebar Verification Event Trigger
    sidebarPnrBtn.onclick = async () => {
        const inputPnr = sidebarPnrInput.value.trim();
        if (!inputPnr || inputPnr.length !== 10 || isNaN(inputPnr)) {
            alert("Please enter a valid 10-digit numerical PNR.");
            return;
        }

        sidebarPnrBtn.textContent = "Verifying...";
        try {
            const response = await fetch('http://localhost:8000/api/bookings');
            const result = await response.json();
            sidebarPnrBtn.textContent = "Verify";
            
            if (result.status === 'success' && result.data) {
                const matched = result.data.find(b => b.pnr_number === inputPnr);
                if (matched) {
                    sidebarPnrInput.value = '';
                    isPaid = true; // Confirmed booking is already paid
                    openTicketModal(matched);
                } else {
                    alert(`PNR Number ${inputPnr} not registered in SQLite core registry.`);
                }
            }
        } catch (err) {
            console.error("Error validating sidebar PNR", err);
            sidebarPnrBtn.textContent = "Verify";
            alert("Signal breakdown checking SQLite records. Is server active?");
        }
    };

    // NEW: Transit Progress Tracker Updater inside Chat Header
    const updateTransitStepper = (stepIndex) => {
        document.querySelectorAll('.transit-stepper .step').forEach((el, index) => {
            if (index === stepIndex) {
                el.classList.add('active');
            } else {
                el.classList.remove('active');
            }
        });
    };

    // Sidebar Toggle
    toggleSidebarBtn.onclick = () => {
        dashboardContainer.classList.toggle('sidebar-collapsed');
        dashboardContainer.classList.toggle('sidebar-active');
    };

    newChatBtn.onclick = () => {
        startNewSession();
    };

    const scrollToBottom = () => {
        chatWindow.scrollTo({
            top: chatWindow.scrollHeight,
            behavior: 'smooth'
        });
    };

    // Simple Markdown Parser
    const parseMarkdown = (text) => {
        let cleanText = text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\[\d+\]/g, '')
            .trim();
        
        cleanText = cleanText.replace(/(\d+\.)\s/g, '<br><br><strong>$1</strong> ');
        cleanText = cleanText.replace(/\n/g, '<br>');
        
        return cleanText;
    };

    // Create minimal flat train card
    const createTrainCard = (train) => {
        const card = document.createElement('div');
        card.className = 'train-card';
        
        const isAvailable = train.availability.includes('AVAILABLE');
        const isRac = train.availability.includes('RAC');
        
        card.innerHTML = `
            <div class="train-header">
                <div class="train-info">
                    <h3>${train.train_name} <span class="train-num">#${train.train_number}</span></h3>
                </div>
                <div class="availability ${isAvailable ? 'available' : (isRac ? 'rac' : '')}">
                    ${train.availability}
                </div>
            </div>
            <div class="train-time-row">
                <div class="time-box">
                    <span class="time">${train.departure_time}</span>
                    <br>
                    <span class="station">Source</span>
                </div>
                <div class="duration-line">
                    <span class="duration-text">${train.duration}</span>
                </div>
                <div class="time-box" style="text-align: right;">
                    <span class="time">${train.arrival_time}</span>
                    <br>
                    <span class="station">Destination</span>
                </div>
            </div>
            <div class="train-footer">
                <div class="fare-box">
                    <span class="label">Estimated Fare</span>
                    <br>
                    <span class="amount">₹${train.fare_estimate}</span>
                </div>
                <button class="book-btn" onclick="window.initiateBooking('${train.train_number}', '${train.train_name}')">Book Now</button>
            </div>
        `;
        return card;
    };

    window.initiateBooking = (num, name) => {
        updateTransitStepper(2); // Step 2: Passenger/Berth Assignment
        userInput.value = `Book ticket for train ${num} (${name}) for passenger John Doe, age 28, class 3A for 2026-05-25`;
        userInput.focus();
        scrollToBottom();
    };

    // Create minimal confirmation card
    const createBookingCard = (data) => {
        const card = document.createElement('div');
        card.className = 'booking-success-inline';
        
        card.innerHTML = `
            <div class="conf-circle">✓</div>
            <div class="success-heading">Ticket Confirmed</div>
            <div class="success-desc">Your reservation on <strong>EXP #${data.train_number}</strong> has been secured for ${data.date}.</div>
            <div class="pnr-stamp-card">
                <span class="lbl">PNR NUMBER</span>
                <span class="val">${data.pnr_number}</span>
            </div>
            <div style="font-size: 0.8rem; width: 100%; border-top: var(--border-thin); padding-top: 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 6px; text-align: left; color: var(--text-secondary);">
                <div><span>PASSENGER:</span> <strong style="color: var(--text-primary);">${data.passenger} (${data.age})</strong></div>
                <div><span>CLASS/COACH:</span> <strong style="color: var(--text-primary);">${data.travel_class}/${data.coach}</strong></div>
                <div><span>BERTH ASSIGNED:</span> <strong style="color: var(--text-primary);">Seat ${data.berth}</strong></div>
                <div><span>STATUS:</span> <strong style="color: var(--success-emerald);">CNF (Confirmed)</strong></div>
            </div>
        `;
        return card;
    };

    // NEW: Render flat dynamic weather badge inside Itinerary card
    const generateWeatherCardHtml = (destination) => {
        const city = destination.toLowerCase().trim();
        
        let weatherData = {
            temp: "27°C",
            state: "Clear Sky 🌤️",
            advice: "Ideal travel weather. We recommend standard comfortable walking attire.",
            themeClass: "weather-cool"
        };

        if (city.includes("jaipur")) {
            weatherData = {
                temp: "38°C",
                state: "Desert Sun ☀️",
                advice: "Dry daytime heat. We recommend wearing <strong>light cotton attire</strong> and carrying shades.",
                themeClass: "weather-warm"
            };
        } else if (city.includes("delhi")) {
            weatherData = {
                temp: "32°C",
                state: "Warm Breeze 🌤️",
                advice: "Mild conditions. We recommend breathable attire and carrying a folding umbrella.",
                themeClass: "weather-warm"
            };
        } else if (city.includes("mumbai")) {
            weatherData = {
                temp: "29°C",
                state: "Coastal Monsoon 🌧️",
                advice: "Humid tropical air. We recommend wearing <strong>quick-dry fabrics</strong> and keeping a raincoat handy.",
                themeClass: "weather-cool"
            };
        }

        return `
            <div class="weather-card ${weatherData.themeClass}">
                <div class="weather-left">
                    <span class="weather-icon">🌡️</span>
                    <div>
                        <div class="weather-temp">${weatherData.temp}</div>
                        <div class="weather-state">${weatherData.state}</div>
                    </div>
                </div>
                <div class="weather-advice">${weatherData.advice}</div>
            </div>
        `;
    };

    // Create Sightseeing Itinerary card with dynamic Weather and Audio narration triggers
    const createItineraryCard = (destination, details) => {
        const card = document.createElement('div');
        card.className = 'itinerary-card';
        
        // 1. Dynamic weather card
        const weatherHtml = generateWeatherCardHtml(destination);

        // 2. Attractions lists with minimal audio players
        let highlightsHtml = '';
        if (details.highlights) {
            highlightsHtml = `
                <div class="itinerary-section highlights">
                    <span class="section-lbl">Historical Sights</span>
                    <div class="highlights-pills" style="margin-bottom: 8px;">
                        ${details.highlights.map(h => `<span class="pill">${h}</span>`).join('')}
                    </div>
                    
                    <!-- NEW: Attraction Audio Narration Player -->
                    <div class="audio-guide-player">
                        <div class="audio-guide-info">
                            <span class="audio-guide-title">${details.highlights[0]} Tour</span>
                            <span class="audio-guide-status-text" id="guide-status-${details.highlights[0].replace(/\s+/g, '')}">Audio Concierge Available</span>
                        </div>
                        <div class="audio-guide-controls">
                            <button class="audio-play-btn" onclick="window.toggleAudioGuide('${details.highlights[0].replace(/'/g, "\\'")}', '${destination}')">
                                🔊 Play Guide
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }

        let foodHtml = '';
        if (details.foods) {
            foodHtml = `
                <div class="itinerary-section foods">
                    <span class="section-lbl">Local Culinary specialties</span>
                    <div class="foods-pills">
                        ${details.foods.map(f => `<span class="pill">${f}</span>`).join('')}
                    </div>
                </div>
            `;
        }

        let tipsHtml = '';
        if (details.tips) {
            tipsHtml = `
                <div style="font-size: 0.8rem; background: rgba(255,255,255,0.01); border: var(--border-thin); border-radius: 8px; padding: 12px; color: var(--text-secondary); line-height: 1.5;">
                    <div style="font-weight: 700; color: var(--accent-cyan); font-size: 0.72rem; text-transform: uppercase; margin-bottom: 4px;">Concierge Tip</div>
                    <div>${details.tips}</div>
                </div>
            `;
        }

        let scheduleHtml = '';
        if (details.schedule) {
            scheduleHtml = `
                <div class="itinerary-section schedule">
                    <span class="section-lbl">Concierge day plan</span>
                    <div class="schedule-grid">
                        ${details.schedule.map(d => `
                            <div class="schedule-day">
                                <div class="day-title">
                                    <span class="day-badge">Day ${d.day}</span>
                                    <span>${d.title}</span>
                                </div>
                                <ul class="day-activities">
                                    ${d.activities.map(a => `<li>${a}</li>`).join('')}
                                </ul>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        card.innerHTML = `
            <div class="itinerary-header">
                <span class="itinerary-icon">🗺️</span>
                <h3>Tourist Concierge: <span class="dest-name">${destination}</span></h3>
            </div>
            ${weatherHtml}
            ${highlightsHtml}
            ${foodHtml}
            ${tipsHtml}
            ${scheduleHtml}
        `;
        return card;
    };

    // NEW: Speak historical narration overviews dynamically
    window.toggleAudioGuide = (attraction, city) => {
        const idSafe = attraction.replace(/\s+/g, '');
        const btn = document.querySelector(`.audio-play-btn`);
        const statusLbl = document.getElementById(`guide-status-${idSafe}`);

        if (activeAudioGuideUtterance) {
            // Stop playing
            window.speechSynthesis.cancel();
            activeAudioGuideUtterance = null;
            btn.innerHTML = "🔊 Play Guide";
            btn.classList.remove('playing');
            statusLbl.textContent = "Audio Concierge Available";
            return;
        }

        // Establish 3-sentence custom sightseeing narratives
        let tourText = `Welcome to the historical tour of ${attraction} in beautiful ${city}. This architectural masterpiece represents centuries of rich local heritage and incredible craftsmanship. Our travel concierge highly recommends exploring its inner courtyard early in the morning to capture the beautiful ambient light.`;
        
        if (attraction.toLowerCase().includes("hawa mahal")) {
            tourText = "Welcome to Hawa Mahal, the Palace of Winds in Jaipur. Built in 1799 by Maharaja Sawai Pratap Singh, this stunning five-story pyramid monument contains 953 small casements or windows. These screens allowed royal ladies to observe daily street festivities without being seen from the outside.";
        } else if (attraction.toLowerCase().includes("red fort")) {
            tourText = "Welcome to the Red Fort, an iconic symbol of historic Delhi. Commissioned by Emperor Shah Jahan in 1638, its massive red sandstone walls reflect the pinnacle of Mughal architectural brilliance. Today, it stands as a UNESCO World Heritage site and a proud anchor of India's independence celebrations.";
        } else if (attraction.toLowerCase().includes("gateway of india")) {
            tourText = "Welcome to the Gateway of India, Mumbai's prominent harbor monument. Built in 1924 to commemorate the landing of King George the Fifth, this grand archway fuses Roman triumphal styles with traditional Gujarati details, welcoming travelers along the Arabian Sea.";
        }

        const utterance = new SpeechSynthesisUtterance(tourText);
        const voices = window.speechSynthesis.getVoices();
        let selectedVoice = voices.find(v => v.lang.includes('en-IN') || v.lang.includes('en-GB'));
        if (!selectedVoice) selectedVoice = voices.find(v => v.lang.includes('en'));
        if (selectedVoice) utterance.voice = selectedVoice;

        utterance.onstart = () => {
            activeAudioGuideUtterance = utterance;
            btn.innerHTML = "⏹️ Stop Guide";
            btn.classList.add('playing');
            statusLbl.textContent = "🔊 NARRATING HISTORY...";
        };

        utterance.onend = () => {
            activeAudioGuideUtterance = null;
            btn.innerHTML = "🔊 Play Guide";
            btn.classList.remove('playing');
            statusLbl.textContent = "Audio Concierge Available";
        };

        utterance.onerror = () => {
            activeAudioGuideUtterance = null;
            btn.innerHTML = "🔊 Play Guide";
            btn.classList.remove('playing');
            statusLbl.textContent = "Audio Concierge Available";
        };

        window.speechSynthesis.cancel(); // Stop anything active
        window.speechSynthesis.speak(utterance);
    };

    // Core Message Rendering function
    const addMessage = (text, isUser = false, uiData = null, triggerSpeech = true) => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${isUser ? 'user-message' : 'ai-message'}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        if (isUser) {
            avatar.textContent = '👤';
        } else {
            const miniLogo = document.createElement('img');
            miniLogo.src = 'logo.png';
            avatar.appendChild(miniLogo);
        }

        const contentWrapper = document.createElement('div');
        contentWrapper.className = 'content-wrapper';

        const content = document.createElement('div');
        content.className = 'content';

        const uiDataRegex = /```ui-data\s*([\s\S]*?)\s*```/;
        const match = text.match(uiDataRegex);
        
        if (match) {
            if (!uiData) {
                try {
                    uiData = JSON.parse(match[1]);
                } catch (e) {
                    console.error("UI Data parsing error", e);
                }
            }
            text = text.replace(uiDataRegex, '').trim();
        }

        content.innerHTML = parseMarkdown(text);
        
        msgDiv.appendChild(avatar);
        contentWrapper.appendChild(content);

        // Render Special Rich Cards
        if (uiData) {
            if (uiData.type === 'train_list' && uiData.trains) {
                updateTransitStepper(1); // Step 1: Select Train Class / Fare
                uiData.trains.forEach(t => {
                    contentWrapper.appendChild(createTrainCard(t));
                });
            } else if (uiData.type === 'booking_success' && uiData.data) {
                activeBookingData = uiData.data; 
                isPaid = false; // Reset paid status for new bookings
                contentWrapper.appendChild(createBookingCard(uiData.data));
                
                updateTransitStepper(3); // Step 3: Ticket Confirmations
                
                if (triggerSpeech) {
                    setTimeout(() => {
                        openPaymentModal(uiData.data);
                    }, 1200);
                }
            } else if (uiData.type === 'itinerary' && uiData.data) {
                contentWrapper.appendChild(createItineraryCard(uiData.destination, uiData.data));
            }

            // Render Follow-up interactive buttons
            if (uiData.buttons && uiData.buttons.length > 0) {
                const btnContainer = document.createElement('div');
                btnContainer.className = 'chat-buttons';
                uiData.buttons.forEach(btnText => {
                    const btn = document.createElement('button');
                    btn.className = 'chat-btn';
                    btn.textContent = btnText;
                    btn.onclick = () => {
                        if (btnText === 'Download Ticket' && activeBookingData) {
                            if (!isPaid) {
                                openPaymentModal(activeBookingData);
                            } else {
                                openTicketModal(activeBookingData);
                            }
                        } else if (btnText === 'View Coach Map' && activeBookingData) {
                            openSeatMapModal(activeBookingData);
                        } else {
                            userInput.value = btnText;
                            chatForm.dispatchEvent(new Event('submit'));
                        }
                    };
                    btnContainer.appendChild(btn);
                });
                contentWrapper.appendChild(btnContainer);
            }
        }

        msgDiv.appendChild(contentWrapper);
        chatWindow.appendChild(msgDiv);
        scrollToBottom();

        if (!isUser && triggerSpeech && ttsEnabled) {
            speakText(text);
        }
    };

    // Chat Submission Form Handler
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const message = userInput.value.trim();
        if (!message) return;

        // Stop speaking immediately when submitting a new message
        window.speechSynthesis.cancel();

        addMessage(message, true);
        userInput.value = '';
        
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
            addMessage(data.reply, false, data.ui_data);
            
            loadSessions();
            updateBookingStats();

        } catch (error) {
            console.error('API Connection Error:', error);
            typingIndicator.classList.add('hidden');
            addMessage('My apologies. I encountered a signal disruption connecting to the transit core. Please ensure the backend server is running.', false);
        }
    });

    // TTS Voice Assistant Reader
    const speakText = (text) => {
        if (!('speechSynthesis' in window)) return;

        let speakingText = text
            .replace(/<\/?[^>]+(>|$)/g, "") 
            .replace(/```ui-data[\s\S]*?```/g, "") 
            .replace(/[^\w\s\u0900-\u097F.,!?]/g, "") 
            .trim();

        if (!speakingText) return;

        const utterance = new SpeechSynthesisUtterance(speakingText);
        
        const voices = window.speechSynthesis.getVoices();
        let selectedVoice = voices.find(v => v.lang.includes('en-IN') || v.lang.includes('en-GB'));
        if (!selectedVoice) {
            selectedVoice = voices.find(v => v.lang.includes('en'));
        }
        if (selectedVoice) utterance.voice = selectedVoice;

        utterance.rate = 1.05;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
    };

    // Toggle Voice Output
    ttsToggleBtn.onclick = () => {
        ttsEnabled = !ttsEnabled;
        localStorage.setItem('yatra_tts_enabled', ttsEnabled);
        
        if (ttsEnabled) {
            ttsToggleBtn.classList.add('speech-active');
            ttsToggleBtn.querySelector('.btn-text').textContent = "Voice On";
            const lastAiMsg = Array.from(document.querySelectorAll('.ai-message .content')).pop();
            if (lastAiMsg) speakText(lastAiMsg.innerText);
        } else {
            ttsToggleBtn.classList.remove('speech-active');
            ttsToggleBtn.querySelector('.btn-text').textContent = "Voice Off";
            window.speechSynthesis.cancel();
        }
    };

    // Speech-To-Text (STT) Speech Input
    const setupSTT = () => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            micBtn.style.display = 'none';
            return;
        }

        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-IN';

        recognition.onstart = () => {
            isListening = true;
            micBtn.classList.add('listening');
            userInput.placeholder = "Listening attentively...";
        };

        recognition.onerror = (e) => {
            console.error("STT Error:", e);
            stopListening();
        };

        recognition.onend = () => {
            stopListening();
        };

        recognition.onresult = (e) => {
            const transcript = e.results[0][0].transcript;
            userInput.value = transcript;
            userInput.focus();
        };
    };

    const stopListening = () => {
        isListening = false;
        micBtn.classList.remove('listening');
        userInput.placeholder = "Plan your transit, e.g., Find trains from Delhi to Jaipur for May 20...";
        if (recognition) recognition.stop();
    };

    micBtn.onclick = () => {
        if (!recognition) setupSTT();
        if (!recognition) return;

        if (isListening) {
            stopListening();
        } else {
            recognition.start();
        }
    };

    // NEW: Handle berth allocation migration persistence
    const handleBerthChange = async (newBerth) => {
        if (!activeBookingData || !activeBookingData.pnr_number) return;
        
        const pnr = activeBookingData.pnr_number;
        try {
            const response = await fetch(`http://localhost:8000/api/bookings/${pnr}/berth`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ berth: newBerth })
            });
            const result = await response.json();
            if (result.status === 'success') {
                // Update local active record
                activeBookingData.berth = newBerth;
                
                // Redraw modal headers
                document.getElementById('seat-map-berth-info').textContent = newBerth;
                const types = ["SU", "LB", "MB", "UB", "LB", "MB", "UB", "SL"];
                const index = newBerth % 8;
                const berthType = types[index];
                const typeLabels = {
                    "LB": "Lower Berth",
                    "MB": "Middle Berth",
                    "UB": "Upper Berth",
                    "SL": "Side Lower",
                    "SU": "Side Upper"
                };
                document.getElementById('seat-map-type-info').textContent = typeLabels[berthType] || "Berth Seat";
                
                // Redraw seating grid
                const coachGridContainer = document.getElementById('coach-grid-container');
                coachGridContainer.innerHTML = generateCoachCompartmentSvg(newBerth);
                
                // Re-bind listeners on redrawn grid
                bindSeatMapClicks(coachGridContainer);
                
                // Redraw the printable ticket modal if it's currently open (so updates sync)
                if (!ticketModal.classList.contains('hidden')) {
                    openTicketModal(activeBookingData);
                }
                
                // Add system trace in chat feed
                addMessage(`System Alert: Dynamic seat reallocation persisted to SQLite database. Passenger migrated to Berth ${newBerth} (${typeLabels[berthType]}).`, false, null, false);
                
                // Sync sidebar active booking records & stats
                await updateBookingStats();
                await loadSessions();
            } else {
                alert("Failed to update seat assignment. Try again.");
            }
        } catch (err) {
            console.error("Error updating berth allocation", err);
            alert("Error contacting the ticketing server. Is it online?");
        }
    };

    const bindSeatMapClicks = (container) => {
        const seatGroups = container.querySelectorAll('.seat-group');
        seatGroups.forEach(group => {
            const berthNum = parseInt(group.getAttribute('data-berth-number'));
            const rect = group.querySelector('.seat-rect');
            
            if (rect.classList.contains('available')) {
                group.onclick = async () => {
                    await handleBerthChange(berthNum);
                };
            }
        });
    };

    // Graphical coach SVG map generator
    const openSeatMapModal = (data) => {
        activeBookingData = data;
        document.getElementById('seat-map-train-info').textContent = `EXP #${data.train_number}`;
        document.getElementById('seat-map-berth-info').textContent = data.berth;
        document.getElementById('seat-map-coach-info').textContent = data.coach;
        
        const bNum = parseInt(data.berth) || 23;
        const types = ["SU", "LB", "MB", "UB", "LB", "MB", "UB", "SL"];
        const index = bNum % 8;
        const berthType = types[index];
        
        const typeLabels = {
            "LB": "Lower Berth",
            "MB": "Middle Berth",
            "UB": "Upper Berth",
            "SL": "Side Lower",
            "SU": "Side Upper"
        };
        document.getElementById('seat-map-type-info').textContent = typeLabels[berthType] || "Berth Seat";

        const coachGridContainer = document.getElementById('coach-grid-container');
        coachGridContainer.innerHTML = generateCoachCompartmentSvg(bNum);
        
        // Bind click triggers
        bindSeatMapClicks(coachGridContainer);
        
        seatMapModal.classList.remove('hidden');
    };

    const generateCoachCompartmentSvg = (selectedBerth) => {
        const compIndex = Math.floor((selectedBerth - 1) / 8);
        const compStart = compIndex * 8 + 1;
        
        const cabinBerths = [
            { number: compStart, type: 'LB', x: 40, y: 30 },
            { number: compStart + 1, type: 'MB', x: 40, y: 70 },
            { number: compStart + 2, type: 'UB', x: 40, y: 110 },
            
            { number: compStart + 3, type: 'LB', x: 190, y: 30 },
            { number: compStart + 4, type: 'MB', x: 190, y: 70 },
            { number: compStart + 5, type: 'UB', x: 190, y: 110 },
            
            { number: compStart + 6, type: 'SL', x: 340, y: 30 },
            { number: compStart + 7, type: 'SU', x: 340, y: 110 }
        ];

        let svgContent = `
            <svg class="coach-svg" viewBox="0 0 460 200" xmlns="http://www.w3.org/2000/svg">
                <rect x="10" y="10" width="440" height="180" rx="8" fill="#0b0e14" stroke="rgba(255,255,255,0.06)" stroke-width="1.5"/>
                
                <rect x="290" y="12" width="30" height="176" fill="rgba(255,255,255,0.005)" class="coach-aisle"/>
                <line x1="290" y1="12" x2="290" y2="188" stroke="rgba(255,255,255,0.04)" stroke-dasharray="2"/>
                <line x1="320" y1="12" x2="320" y2="188" stroke="rgba(255,255,255,0.04)" stroke-dasharray="2"/>
                
                <line x1="10" y1="150" x2="290" y2="150" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>
                <line x1="140" y1="12" x2="140" y2="150" stroke="rgba(255,255,255,0.04)" stroke-width="1" stroke-dasharray="2"/>
        `;

        cabinBerths.forEach(b => {
            const isTarget = b.number === selectedBerth;
            const isOccupied = !isTarget && (b.number % 3 === 0 || b.number % 5 === 0);
            
            let seatClass = 'available';
            if (isTarget) seatClass = 'booked';
            else if (isOccupied) seatClass = 'occupied';
            
            svgContent += `
                <g class="seat-group" data-berth-number="${b.number}" style="${seatClass === 'available' || seatClass === 'booked' ? 'cursor: pointer;' : 'cursor: not-allowed;'}">
                    <rect x="${b.x}" y="${b.y}" width="80" height="30" rx="4" class="seat-rect ${seatClass}" data-berth-number="${b.number}"/>
                    <text x="${b.x + 40}" y="${b.y + 18}" text-anchor="middle" class="seat-text ${isTarget ? 'booked' : ''}">
                        ${b.number} [${b.type}]
                    </text>
                </g>
            `;
        });

        svgContent += `
                <text x="230" y="172" text-anchor="middle" fill="var(--text-secondary)" font-size="9" font-weight="bold" letter-spacing="0.5">
                    COMPARTMENT ${compIndex + 1}
                </text>
            </svg>
        `;
        return svgContent;
    };

    // ==========================================================================
    // UPI PAYMENT SANDBOX MODAL MANAGEMENT
    // ==========================================================================
    const openPaymentModal = (data) => {
        activeBookingData = data;
        payPassengerName.textContent = data.passenger || data.passenger_name || "Passenger";
        payRouteInfo.textContent = `EXP #${data.train_number} - Class ${data.travel_class}`;
        payAmountInfo.textContent = "INR 1,250";
        
        // Reset pay submit button
        paySubmitBtn.innerHTML = "Pay Securely";
        paySubmitBtn.disabled = false;
        paySubmitBtn.classList.remove('processing');
        
        // Select GPay by default
        const upiApps = document.querySelectorAll('.upi-app');
        if (upiApps.length > 0) {
            upiApps.forEach(a => a.classList.remove('selected'));
            upiApps[0].classList.add('selected');
        }
        
        // Step 3: Ticket Confirmations & Checkout Stage
        updateTransitStepper(3);
        
        paymentModal.classList.remove('hidden');
    };

    closePaymentBtn.onclick = () => {
        paymentModal.classList.add('hidden');
    };

    // Wire app buttons inside row
    const upiApps = document.querySelectorAll('.upi-app');
    upiApps.forEach(app => {
        app.onclick = () => {
            upiApps.forEach(a => a.classList.remove('selected'));
            app.classList.add('selected');
        };
    });

    paySubmitBtn.onclick = () => {
        paySubmitBtn.disabled = true;
        paySubmitBtn.classList.add('processing');
        paySubmitBtn.innerHTML = `<span class="pay-btn-spinner"></span> Simulating payment...`;
        
        setTimeout(() => {
            paymentModal.classList.add('hidden');
            isPaid = true; // Mark as paid
            
            // Success burst & launch pass
            startConfetti();
            addMessage("🎉 Payment authorized successfully! Generating boarding pass...", false, null, false);
            
            setTimeout(() => {
                openTicketModal(activeBookingData);
            }, 800);
        }, 1500);
    };

    closeSeatMapBtn.onclick = () => seatMapModal.classList.add('hidden');
    closeTicketModalBtn.onclick = () => {
        ticketModal.classList.add('hidden');
        updateTransitStepper(3); // Reset to confirm step
    };

    // Printable Boarding Pass dialog
    const openTicketModal = (data) => {
        activeBookingData = data;
        const printableWrapper = document.getElementById('ticket-printable-wrapper');
        
        updateTransitStepper(4); // Step 4: Ready to Board (Boarding Pass review)

        printableWrapper.innerHTML = `
            <div class="premium-ticket-card" id="printable-ticket">
                <div class="t-banner">
                    <div class="t-banner-logo">
                        <img src="logo.png" style="width: 20px; height: 20px;" alt="logo">
                        <span>YatraAI Concierge</span>
                    </div>
                    <div class="t-pnr-container">
                        <span class="lbl">PNR NUMBER</span>
                        <br>
                        <span class="val">${data.pnr_number}</span>
                    </div>
                </div>
                
                <div class="t-body">
                    <div class="t-route-row">
                        <div class="t-station-info" style="text-align: left;">
                            <span class="city" style="color: var(--accent-cyan);">DELHI</span>
                            <div class="station-code">NEW DELHI STN • NDLS</div>
                        </div>
                        <div class="t-route-vector">
                            <div class="t-vector-line"></div>
                            <span class="duration">SCHEDULED TRANSIT</span>
                        </div>
                        <div class="t-station-info" style="text-align: right;">
                            <span class="city" style="color: var(--accent-purple);">JAIPUR</span>
                            <div class="station-code">JAIPUR JUNCTION • JP</div>
                        </div>
                    </div>
                    
                    <div class="t-details-grid">
                        <div class="t-grid-item">
                            <span class="lbl">TRAIN DETAILS</span>
                            <br>
                            <span class="val">EXP #${data.train_number}</span>
                        </div>
                        <div class="t-grid-item">
                            <span class="lbl">CLASS / COACH</span>
                            <br>
                            <span class="val">${data.travel_class} / ${data.coach}</span>
                        </div>
                        <div class="t-grid-item">
                            <span class="lbl">DATE OF TRANSIT</span>
                            <br>
                            <span class="val">${data.date}</span>
                        </div>
                        <div class="t-grid-item">
                            <span class="lbl">BERTH ASSIGNED</span>
                            <br>
                            <span class="val">Seat ${data.berth}</span>
                        </div>
                        <div class="t-grid-item">
                            <span class="lbl">BOOKING STATUS</span>
                            <br>
                            <span class="val" style="color: var(--success-emerald); font-weight: bold;">CNF (CONFIRMED)</span>
                        </div>
                        <div class="t-grid-item">
                            <span class="lbl">BOARDING TIME</span>
                            <br>
                            <span class="val">16:30 HRS</span>
                        </div>
                    </div>
                </div>
                
                <div class="t-separator"></div>
                
                <div class="t-footer">
                    <div class="t-passenger-card">
                        <span class="lbl">PASSENGER RECORD</span>
                        <br>
                        <span class="val">${data.passenger}</span>
                        <br>
                        <span class="age">Male • Age ${data.age}</span>
                    </div>
                    <div class="t-barcode-container" style="text-align: right;">
                        <div class="barcode-visual"></div>
                        <span class="barcode-text">PNR-${data.pnr_number}</span>
                    </div>
                </div>
            </div>
        `;
        
        ticketModal.classList.remove('hidden');
    };

    // Client-Side Canvas Boarding Pass print/download
    downloadTicketBtn.onclick = () => {
        if (!activeBookingData) return;
        const d = activeBookingData;
        
        const canvas = document.createElement('canvas');
        canvas.width = 600;
        canvas.height = 420;
        const ctx = canvas.getContext('2d');
        
        ctx.fillStyle = '#080c14';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.lineWidth = 1;
        ctx.strokeRect(10, 10, canvas.width - 20, canvas.height - 20);
        
        ctx.fillStyle = '#0e1320';
        ctx.fillRect(10, 10, canvas.width - 20, 70);
        
        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 18px "Space Grotesk", sans-serif';
        ctx.fillText('YatraAI Concierge', 32, 50);
        
        ctx.fillStyle = '#94a3b8';
        ctx.font = '8px "Outfit", sans-serif';
        ctx.fillText('PNR NUMBER', 460, 40);
        
        ctx.fillStyle = '#06b6d4';
        ctx.font = 'bold 16px "Courier New", monospace';
        ctx.fillText(d.pnr_number, 460, 60);
        
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.beginPath();
        ctx.moveTo(10, 80);
        ctx.lineTo(canvas.width - 10, 80);
        ctx.stroke();

        ctx.fillStyle = '#06b6d4';
        ctx.font = 'bold 20px "Space Grotesk", sans-serif';
        ctx.fillText('DELHI (NDLS)', 32, 125);
        
        ctx.fillStyle = '#94a3b8';
        ctx.font = '9px "Outfit", sans-serif';
        ctx.fillText('NEW DELHI STN', 32, 140);
        
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(200, 128);
        ctx.lineTo(380, 128);
        ctx.stroke();
        
        ctx.fillStyle = '#94a3b8';
        ctx.font = '8px "Outfit", sans-serif';
        ctx.fillText('SCHEDULED TRANSIT', 250, 120);

        ctx.fillStyle = '#a855f7';
        ctx.font = 'bold 20px "Space Grotesk", sans-serif';
        ctx.fillText('JAIPUR (JP)', 420, 125);
        
        ctx.fillStyle = '#94a3b8';
        ctx.font = '9px "Outfit", sans-serif';
        ctx.fillText('JAIPUR JUNCTION', 420, 140);

        ctx.fillStyle = '#0e1320';
        ctx.fillRect(32, 170, canvas.width - 64, 110);
        ctx.strokeStyle = 'rgba(255,255,255,0.05)';
        ctx.strokeRect(32, 170, canvas.width - 64, 110);
        
        const drawGridItem = (lbl, val, x, y, valColor = '#f8fafc') => {
            ctx.fillStyle = '#94a3b8';
            ctx.font = '8px "Outfit", sans-serif';
            ctx.fillText(lbl, x, y);
            
            ctx.fillStyle = valColor;
            ctx.font = 'bold 12px "Outfit", sans-serif';
            ctx.fillText(val, x, y + 16);
        };
        
        drawGridItem('TRAIN DETAILS', `EXP #${d.train_number}`, 50, 192);
        drawGridItem('CLASS / COACH', `${d.travel_class} / ${d.coach}`, 230, 192);
        drawGridItem('DATE OF TRANSIT', d.date, 410, 192);
        
        drawGridItem('BERTH ASSIGNED', `Seat ${d.berth}`, 50, 242);
        drawGridItem('BOOKING STATUS', 'CNF (CONFIRMED)', 230, 242, '#10b981');
        drawGridItem('BOARDING TIME', '16:30 HRS', 410, 242);

        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(32, 305);
        ctx.lineTo(canvas.width - 32, 305);
        ctx.stroke();
        ctx.setLineDash([]); 

        ctx.fillStyle = '#94a3b8';
        ctx.font = '8px "Outfit", sans-serif';
        ctx.fillText('PASSENGER RECORD', 32, 335);
        
        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 16px "Space Grotesk", sans-serif';
        ctx.fillText(d.passenger, 32, 355);
        
        ctx.fillStyle = '#94a3b8';
        ctx.font = '10px "Outfit", sans-serif';
        ctx.fillText(`Male • Age ${d.age}`, 32, 372);

        ctx.fillStyle = '#ffffff';
        ctx.fillRect(440, 325, 120, 30);
        
        ctx.fillStyle = '#000000';
        let barOffset = 446;
        const strips = [2, 4, 1, 3, 5, 2, 4, 1, 3, 2, 4, 5, 1, 3];
        strips.forEach(width => {
            ctx.fillRect(barOffset, 329, width, 22);
            barOffset += width + 2;
        });
        
        ctx.fillStyle = '#94a3b8';
        ctx.font = '8px monospace';
        ctx.fillText(`PNR-${d.pnr_number}`, 456, 370);

        const image = canvas.toDataURL("image/png").replace("image/png", "image/octet-stream");
        const link = document.createElement('a');
        link.download = `YatraAI-Ticket-${d.pnr_number}.png`;
        link.href = image;
        link.click();
    };

    // Confetti System
    const startConfetti = () => {
        const canvas = document.getElementById('confetti-canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        
        let particles = [];
        const colors = ['#06b6d4', '#6366f1', '#a855f7', '#10b981', '#f59e0b'];
        
        for (let i = 0; i < 80; i++) { // Reduced particle count for minimalist clean aesthetics
            particles.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height - canvas.height,
                r: Math.random() * 4 + 3,
                d: Math.random() * canvas.height,
                color: colors[Math.floor(Math.random() * colors.length)],
                tilt: Math.random() * 8 - 4,
                tiltAngleIncremental: Math.random() * 0.05 + 0.02,
                tiltAngle: 0
            });
        }
        
        const draw = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            particles.forEach((p, index) => {
                p.tiltAngle += p.tiltAngleIncremental;
                p.y += (Math.cos(p.d) + 3 + p.r / 2) / 2;
                p.x += Math.sin(p.tiltAngle);
                p.tilt = Math.sin(p.tiltAngle - index / 3) * 10;
                
                ctx.beginPath();
                ctx.lineWidth = p.r;
                ctx.strokeStyle = p.color;
                ctx.moveTo(p.x + p.tilt + p.r / 2, p.y);
                ctx.lineTo(p.x + p.tilt, p.y + p.tilt + p.r / 2);
                ctx.stroke();
            });
            
            particles = particles.filter(p => p.y < canvas.height);
            
            if (particles.length > 0) {
                requestAnimationFrame(draw);
            } else {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }
        };
        
        draw();
    };

    window.addEventListener('resize', () => {
        const canvas = document.getElementById('confetti-canvas');
        if (canvas) {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }
    });

    initPortal();
});
