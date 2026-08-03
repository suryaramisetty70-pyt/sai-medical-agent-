$(document).ready(function () {
    // -------------------------------------------------------------------------
    // 1. Theme Management (Light / Dark Mode)
    // -------------------------------------------------------------------------
    const savedTheme = localStorage.getItem('nikki_medical_theme') || 'light-theme';
    $('body').removeClass('light-theme dark-theme').addClass(savedTheme);
    updateThemeIcon(savedTheme);

    $('#theme-toggle-btn').click(function (e) {
        e.preventDefault();
        const currentTheme = $('body').hasClass('dark-theme') ? 'dark-theme' : 'light-theme';
        const newTheme = currentTheme === 'dark-theme' ? 'light-theme' : 'dark-theme';
        $('body').removeClass('light-theme dark-theme').addClass(newTheme);
        localStorage.setItem('nikki_medical_theme', newTheme);
        updateThemeIcon(newTheme);
    });

    function updateThemeIcon(theme) {
        if (theme === 'dark-theme') {
            $('#theme-toggle-btn').html('<i class="fas fa-sun"></i>');
        } else {
            $('#theme-toggle-btn').html('<i class="fas fa-moon"></i>');
        }
    }

    // -------------------------------------------------------------------------
    // 2. Tab Navigation
    // -------------------------------------------------------------------------
    $('.nav-item').click(function (e) {
        e.preventDefault();
        const targetTab = $(this).data('tab');
        $('.nav-item').removeClass('active');
        $(this).addClass('active');

        $('.tab-content').removeClass('active');
        $('#' + targetTab).addClass('active');

        if (targetTab === 'tab-terms') {
            loadMedicalEncyclopedia();
        }
    });

    // Mobile Sidebar Toggle
    $('#mobile-menu-btn').click(function (e) {
        e.preventDefault();
        $('.sidebar').toggleClass('mobile-open');
    });

    // -------------------------------------------------------------------------
    // 3. AI Chat & Symptom Processing
    // -------------------------------------------------------------------------
    $('#chat-form').submit(function (e) {
        e.preventDefault();
        let message = $('#user-input').val().trim();
        let language = $('#language-select').val();

        if (!message) return;

        appendUserMessage(message);
        $('#user-input').val('');
        scrollToBottom();
        appendTypingIndicator();

        $.ajax({
            url: '/chat',
            type: 'POST',
            data: { message: message, language: language },
            success: function (data) {
                removeTypingIndicator();
                let formattedResponse = data.response;
                if (data.audio) {
                    formattedResponse += ` <i class="fas fa-volume-up audio-icon" data-audio="${data.audio}" title="Listen Audio"></i>`;
                }
                appendBotMessage(formattedResponse, false);

                if (data.is_severe) {
                    $('#emergency-alert').removeClass('d-none');
                } else {
                    $('#emergency-alert').addClass('d-none');
                }

                if (data.audio) {
                    playAudio(data.audio);
                }
                scrollToBottom();
            },
            error: function (xhr) {
                removeTypingIndicator();
                let errorMsg = xhr.responseJSON ? xhr.responseJSON.error : 'Server connection error.';
                appendBotMessage(`**Error:** ${errorMsg}`, false);
                scrollToBottom();
            }
        });
    });

    // -------------------------------------------------------------------------
    // 4. WebRTC Camera & Image Scanner Handler
    // -------------------------------------------------------------------------
    let videoStream = null;
    let currentImageB64 = null;

    $('#start-camera-btn').click(function (e) {
        e.preventDefault();
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
                .then(function (stream) {
                    videoStream = stream;
                    const videoElem = document.getElementById('camera-stream');
                    videoElem.srcObject = stream;
                    $('#camera-stream').removeClass('d-none');
                    $('#camera-placeholder').addClass('d-none');
                    $('#image-preview').addClass('d-none');
                    $('#capture-snapshot-btn').removeClass('d-none');
                    $('#start-camera-btn').html('<i class="fas fa-stop"></i> Stop Camera');
                })
                .catch(function (err) {
                    alert('Camera access denied or unavailable. Please use the Upload Image option.');
                });
        }
    });

    $('#capture-snapshot-btn').click(function (e) {
        e.preventDefault();
        const videoElem = document.getElementById('camera-stream');
        const canvasElem = document.getElementById('camera-canvas');
        const context = canvasElem.getContext('2d');

        canvasElem.width = videoElem.videoWidth || 640;
        canvasElem.height = videoElem.videoHeight || 480;
        context.drawImage(videoElem, 0, 0, canvasElem.width, canvasElem.height);

        currentImageB64 = canvasElem.toDataURL('image/jpeg');

        if (videoStream) {
            videoStream.getTracks().forEach(track => track.stop());
            videoStream = null;
        }

        $('#camera-stream').addClass('d-none');
        $('#image-preview').attr('src', currentImageB64).removeClass('d-none');
        $('#capture-snapshot-btn').addClass('d-none');
        $('#start-camera-btn').html('<i class="fas fa-video"></i> Start Camera');
        $('#analyze-image-btn').prop('disabled', false);
    });

    $('#image-file-input').change(function (e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function (event) {
                currentImageB64 = event.target.result;
                $('#camera-placeholder').addClass('d-none');
                $('#camera-stream').addClass('d-none');
                $('#image-preview').attr('src', currentImageB64).removeClass('d-none');
                $('#analyze-image-btn').prop('disabled', false);
            };
            reader.readAsDataURL(file);
        }
    });

    $('#analyze-image-btn').click(function (e) {
        e.preventDefault();
        if (!currentImageB64) {
            alert('Please start camera & capture snapshot or upload an image file first.');
            return;
        }

        const notes = $('#image-notes-input').val().trim();
        const lang = $('#language-select').val();

        $('#camera-analysis-result').removeClass('d-none').html('<i class="fas fa-spinner fa-spin"></i> Analyzing image features with Visual Pathology Engine...');

        $.ajax({
            url: '/analyze_image',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ image_data: currentImageB64, notes: notes, language: lang }),
            success: function (data) {
                let formattedMarkdown = window.marked ? marked.parse(data.response) : data.response;
                $('#camera-analysis-result').html(formattedMarkdown);
            }
        });
    });

    // -------------------------------------------------------------------------
    // 5. Medicine Search & Drug Interaction Checker
    // -------------------------------------------------------------------------
    $('#search-med-btn').click(function (e) {
        e.preventDefault();
        const query = $('#med-search-input').val().trim();
        const otherMeds = $('#med-other-input').val().trim();

        if (!query) {
            alert('Please enter a medicine name to search.');
            return;
        }

        $('#med-result-box').removeClass('d-none').html('<i class="fas fa-spinner fa-spin"></i> Searching medicine database & checking drug interactions...');

        $.ajax({
            url: '/search_medicine',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ query: query, other_meds: otherMeds }),
            success: function (data) {
                let formattedMarkdown = window.marked ? marked.parse(data.medicine_info) : data.medicine_info;
                $('#med-result-box').html(formattedMarkdown);
            }
        });
    });

    // -------------------------------------------------------------------------
    // 6. AI Clinical Diet & Nutrition Planner Handler
    // -------------------------------------------------------------------------
    $('#generate-diet-btn').click(function (e) {
        e.preventDefault();
        const condition = $('#diet-condition-select').val();
        const age = $('#diet-age').val();
        const weight = $('#diet-weight').val();
        const height = $('#diet-height').val();
        const lang = $('#language-select').val();

        $('#diet-result-box').removeClass('d-none').html('<i class="fas fa-spinner fa-spin"></i> Calculating BMI & generating custom clinical diet plan...');

        $.ajax({
            url: '/generate_diet_plan',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ condition: condition, age: age, weight: weight, height: height, language: lang }),
            success: function (data) {
                let formattedMarkdown = window.marked ? marked.parse(data.diet_plan) : data.diet_plan;
                $('#diet-result-box').html(formattedMarkdown);
            }
        });
    });

    // -------------------------------------------------------------------------
    // 7. AI Lab Report Analyzer
    // -------------------------------------------------------------------------
    $('#analyze-lab-btn').click(function (e) {
        e.preventDefault();
        const testType = $('#lab-type-select').val();
        const value = $('#lab-val-input').val().trim();

        if (!value) {
            alert('Please enter a numeric lab test value.');
            return;
        }

        $('#lab-result-box').removeClass('d-none').html('<i class="fas fa-spinner fa-spin"></i> Analyzing blood test value...');

        $.ajax({
            url: '/analyze_lab_report',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ test_type: testType, value: value }),
            success: function (data) {
                let formattedMarkdown = window.marked ? marked.parse(data.report) : data.report;
                $('#lab-result-box').html(formattedMarkdown);
            }
        });
    });

    // -------------------------------------------------------------------------
    // 8. Live Wikipedia Medical API & Encyclopedia Search
    // -------------------------------------------------------------------------
    $('#wiki-search-btn').click(function (e) {
        e.preventDefault();
        let query = $('#term-search-input').val().trim();
        if (!query) {
            alert('Please enter a disease or medical term to search Wikipedia.');
            return;
        }

        $('#wiki-live-result-box').removeClass('d-none').html('<i class="fas fa-spinner fa-spin"></i> Fetching live article from Wikipedia Medical API...');

        $.ajax({
            url: '/api/wikipedia_search',
            type: 'GET',
            data: { q: query },
            success: function (data) {
                let imgHtml = data.thumbnail ? `<img src="${data.thumbnail}" style="max-width:120px; float:right; border-radius:8px; margin-left:12px;">` : '';
                let wikiHtml = `
                    <h3><i class="fab fa-wikipedia-w"></i> ${escapeHtml(data.title)}</h3>
                    ${imgHtml}
                    <p style="margin-top:8px; font-size:14px; line-height:1.6;">${escapeHtml(data.extract)}</p>
                    <p style="margin-top:12px; font-size:12px;"><strong>Source:</strong> ${data.source} | <a href="${data.url}" target="_blank">Read Full Wikipedia Article <i class="fas fa-external-link-alt"></i></a></p>`;
                $('#wiki-live-result-box').html(wikiHtml);
            }
        });
    });

    function loadMedicalEncyclopedia() {
        let query = $('#term-search-input').val();
        let category = $('#category-filter').val();

        $.ajax({
            url: '/api/medical_terms',
            type: 'GET',
            data: { q: query, category: category },
            success: function (data) {
                renderEncyclopediaCards(data.terms);
            }
        });
    }

    $('#term-search-input').on('keyup', function (e) {
        if (e.key === 'Enter') {
            $('#wiki-search-btn').click();
        } else {
            loadMedicalEncyclopedia();
        }
    });

    $('#category-filter').on('change', loadMedicalEncyclopedia);

    function renderEncyclopediaCards(terms) {
        let container = $('#terms-grid');
        container.empty();

        if (!terms || terms.length === 0) {
            container.html('<p class="text-secondary">No local terms found. Use the <strong>Search Wiki API</strong> button above to query Wikipedia for any medical term!</p>');
            return;
        }

        terms.forEach(function (term) {
            let cardHtml = `
                <div class="term-card">
                    <span class="term-category">${escapeHtml(term.category)}</span>
                    <h3>${escapeHtml(term.name)}</h3>
                    <p><strong>Symptoms:</strong> ${escapeHtml(term.symptoms)}</p>
                    <p><strong>First Aid:</strong> ${escapeHtml(term.first_aid)}</p>
                    <p><strong>When to see doctor:</strong> ${escapeHtml(term.when_to_see_doctor)}</p>
                </div>`;
            container.append(cardHtml);
        });
    }

    // -------------------------------------------------------------------------
    // 9. Complete Unlimited Symptom Checker Suite
    // -------------------------------------------------------------------------
    $('#evaluate-symptoms-btn').click(function (e) {
        e.preventDefault();
        let selectedSymptoms = [];
        $('.symptom-checkboxes input:checked').each(function () {
            selectedSymptoms.push($(this).val());
        });

        let customText = $('#custom-symptom-input').val().trim();
        if (customText) {
            selectedSymptoms.push(customText);
        }

        if (selectedSymptoms.length === 0) {
            alert('Please select at least one symptom or type a custom symptom.');
            return;
        }

        let combinedQuery = selectedSymptoms.join(', ');
        $('#wizard-result').removeClass('d-none').html('<i class="fas fa-spinner fa-spin"></i> Running complete clinical symptom evaluation...');

        let language = $('#language-select').val();
        $.ajax({
            url: '/chat',
            type: 'POST',
            data: { message: `Complete symptom analysis for: ${combinedQuery}`, language: language },
            success: function (data) {
                let parsedMarkdown = window.marked ? marked.parse(data.response) : data.response;
                $('#wizard-result').html(`<h4>Comprehensive Assessment Summary:</h4>${parsedMarkdown}`);
            }
        });
    });

    // -------------------------------------------------------------------------
    // 10. Web Speech Recognition API & Settings
    // -------------------------------------------------------------------------
    let recognition = null;
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        let SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = function () {
            $('#voice-btn').addClass('listening').html('<i class="fas fa-dot-circle"></i>');
        };

        recognition.onresult = function (event) {
            let transcript = event.results[0][0].transcript;
            $('#user-input').val(transcript);
            $('#chat-form').submit();
        };

        recognition.onerror = function () { stopListening(); };
        recognition.onend = function () { stopListening(); };
    }

    $('#voice-btn').click(function (e) {
        e.preventDefault();
        if (recognition) {
            let lang = $('#language-select').val();
            let langMap = { 'en': 'en-US', 'te': 'te-IN', 'ta': 'ta-IN', 'hi': 'hi-IN' };
            recognition.lang = langMap[lang] || 'en-US';
            try { recognition.start(); } catch (e) { recognition.stop(); }
        }
    });

    function stopListening() {
        $('#voice-btn').removeClass('listening').html('<i class="fas fa-microphone"></i>');
    }

    $('#save-api-key-btn').click(function (e) {
        e.preventDefault();
        let key = $('#api-key-input').val().trim();
        $.ajax({
            url: '/set_api_key',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ api_key: key }),
            success: function (data) {
                $('#api-key-status').removeClass('d-none').text(data.message);
                setTimeout(function () { $('#api-key-status').addClass('d-none'); }, 3000);
            }
        });
    });

    // -------------------------------------------------------------------------
    // Helper Functions
    // -------------------------------------------------------------------------
    $(document).on('click', '.audio-icon', function () {
        let audioUrl = $(this).data('audio');
        playAudio(audioUrl);
    });

    function playAudio(audioUrl) {
        if (!audioUrl) return;
        let fullPath = audioUrl.startsWith('/') ? audioUrl : '/' + audioUrl;
        let audio = new Audio(fullPath);
        audio.play().catch(e => console.error(e));
    }

    function appendUserMessage(text) {
        let html = `<div class="msg-row user-row"><div class="avatar user-avatar"><i class="fas fa-user"></i></div><div class="msg-bubble user-bubble">${escapeHtml(text)}</div></div>`;
        $('#chat-viewport').append(html);
    }

    function appendBotMessage(markdownContent) {
        let htmlContent = window.marked ? marked.parse(markdownContent) : markdownContent;
        let html = `<div class="msg-row bot-row"><div class="avatar bot-avatar"><i class="fas fa-user-md"></i></div><div class="msg-bubble bot-bubble">${htmlContent}</div></div>`;
        $('#chat-viewport').append(html);
    }

    function appendTypingIndicator() {
        let html = `<div class="msg-row bot-row" id="typing-row"><div class="avatar bot-avatar"><i class="fas fa-user-md"></i></div><div class="msg-bubble bot-bubble"><i class="fas fa-circle-notch fa-spin"></i> <span>Analyzing medical symptoms...</span></div></div>`;
        $('#chat-viewport').append(html);
        scrollToBottom();
    }

    function removeTypingIndicator() {
        $('#typing-row').remove();
    }

    function scrollToBottom() {
        $('#chat-viewport').scrollTop($('#chat-viewport')[0].scrollHeight);
    }

    function escapeHtml(text) {
        return $('<div>').text(text).html();
    }
});

function sendQuickSymptom(symptomText) {
    $('.nav-item[data-tab="tab-chat"]').click();
    $('#user-input').val(symptomText);
    $('#chat-form').submit();
}
