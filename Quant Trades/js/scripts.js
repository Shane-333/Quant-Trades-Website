document.addEventListener('DOMContentLoaded', function () {
    const body = document.body;
    const toggleModeButton = document.getElementById('toggleMode');

    // Function to apply the mode
    function applyMode(mode) {
        body.classList.remove('light-mode', 'dark-mode');
        body.classList.add(mode);
        localStorage.setItem('displayMode', mode);
    }

    new TradingView.widget({
        "container_id": "tradingview_chart",
        "autosize": true,
        "width": "100%",
        "height": 700, // Increased height for a larger chart
        "symbol": "NASDAQ:AAPL",
        "interval": "D",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "details": true,
        "hotlist": true,
        "calendar": true,
        "news": ["stocktwits", "headlines"],
        "studies": ["Volume@tv-basicstudies"]
    });

    // Load the user's preferred mode from localStorage
    const savedMode = localStorage.getItem('displayMode') || 'light-mode';
    applyMode(savedMode);

    // Toggle the mode when the button is clicked
    if (toggleModeButton) {
        toggleModeButton.addEventListener('click', function () {
            const currentMode = body.classList.contains('light-mode') ? 'light-mode' : 'dark-mode';
            const newMode = currentMode === 'light-mode' ? 'dark-mode' : 'light-mode';
            applyMode(newMode);
        });
    }

    function startBot() {
        fetch('http://localhost:8000/start_lumibot_trend', { method: 'POST' })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                document.getElementById('botStatus').textContent = 'Running';
                console.log(data.message);
                fetchLogs();
            })
            .catch(error => {
                console.error('Error starting the bot:', error);
                document.getElementById('botStatus').textContent = 'Error';
            });
    }

    function stopBot() {
        fetch('http://localhost:8000/stop_lumibot_trend', { method: 'POST' })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                document.getElementById('botStatus').textContent = 'Stopped';
                console.log(data.message);
                fetchLogs();
            })
            .catch(error => {
                console.error('Error stopping the bot:', error);
                document.getElementById('botStatus').textContent = 'Error';
            });
    }

    function fetchLogs() {
        fetch('http://localhost:8000/logs')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                document.getElementById('logs').textContent = data.logs;
            })
            .catch(error => {
                console.error('Error fetching logs:', error);
                document.getElementById('logs').textContent = 'Error fetching logs';
            });
    }

    function updateSymbols() {
        const symbolsInput = document.getElementById('symbolsInput');
        const symbols = symbolsInput.value.split(',').map(s => s.trim());
        fetch('http://localhost:8000/update_symbols', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ symbols })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log(data.message);
        })
        .catch(error => {
            console.error('Error updating symbols:', error);
        });
    }

    window.startBot = startBot;
    window.stopBot = stopBot;
    window.updateSymbols = updateSymbols;

    fetchLogs();
});

/* Event listener for DOM content loaded */
window.addEventListener('DOMContentLoaded', event => {
    // Navbar shrink function
    var navbarShrink = function () {
        const navbarCollapsible = document.body.querySelector('#mainNav');
        if (navbarCollapsible) {
            if (window.scrollY === 0) {
                navbarCollapsible.classList.remove('navbar-shrink');
            } else {
                navbarCollapsible.classList.add('navbar-shrink');
            }
        }
    };

    // Shrink the navbar when page is scrolled
    navbarShrink();
    document.addEventListener('scroll', navbarShrink);

    // Activate Bootstrap scrollspy on the main nav element
    const mainNav = document.body.querySelector('#mainNav');
    if (mainNav) {
        new bootstrap.ScrollSpy(document.body, {
            target: '#mainNav',
            rootMargin: '0px 0px -40%',
        });
    }

    // Collapse responsive navbar when toggler is visible
    const navbarToggler = document.body.querySelector('.navbar-toggler');
    const responsiveNavItems = [].slice.call(document.querySelectorAll('#navbarResponsive .nav-link'));
    responsiveNavItems.forEach(function (responsiveNavItem) {
        responsiveNavItem.addEventListener('click', () => {
            if (window.getComputedStyle(navbarToggler).display !== 'none') {
                navbarToggler.click();
            }
        });
    });
});

// Fetch market data
async function fetchMarketData(symbol) {
    try {
        const response = await fetch(`http://localhost:8000/market_data/${symbol}`);
        if (!response.ok) {
            throw new Error('Failed to fetch: ' + response.statusText);
        }
        const data = await response.json();
        console.log('Market Data:', data);
        return data;
    } catch (error) {
        console.error('Fetch error:', error.message);
        return null;
    }
}

// Start trading function
function startTrading() {
    fetch('http://localhost:8000/start_lumibot_swing_high', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        console.log(data.message);
        alert('Trading Bot Started: ' + data.message); // Optional: alert user
    })
    .catch(error => console.error('Error starting the trading bot:', error));
}

// Stop trading function
function stopTrading() {
    fetch('http://localhost:8000/stop_lumibot_swing_high', {
        method: 'POST'
    })
    .then(response => {
        if (response.ok) {
            console.log('Stop signal sent successfully');
        } else {
            console.log('Failed to send stop signal');
        }
    })
    .catch(error => console.error('Error stopping the trading bot:', error));
}

