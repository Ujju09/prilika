document.addEventListener('DOMContentLoaded', () => {
    // Set default date to today
    document.getElementById('transaction-date').valueAsDate = new Date();
    
    // Initial loads
    fetchQueue();

    
    // Event Listeners
    document.getElementById('process-btn').addEventListener('click', processTransaction);

});



async function processTransaction() {
    const descInput = document.getElementById('transaction-desc');
    const dateInput = document.getElementById('transaction-date');
    const processBtn = document.getElementById('process-btn');
    const indicator = document.getElementById('processing-indicator');
    
    const description = descInput.value.trim();
    if (!description) {
        alert("Please enter a description");
        return;
    }
    
    // Get API Key
    // const apiKey = localStorage.getItem('anthropic_api_key');
    
    // UI State: Running
    processBtn.disabled = true;
    indicator.classList.remove('hidden');
    clearPipeline();
    switchTab('pipeline');
    
    const startTime = Date.now();
    addLog('info', 'UI', 'Processing started...');
    
    try {
        const headers = {
            'Content-Type': 'application/json',
        };


        const response = await fetch('/accounting/api/process/', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                description: description,
                date: dateInput.value
            })
        });
        
        const data = await response.json();
        
        if (data.session_id) {
            // Fetch the full logs for this session
            await pollLogs(data.session_id);
        }
        
        if (data.success) {
            addLog('info', 'UI', `Process completed in ${(Date.now() - startTime)/1000}s`);
            renderPipeline(data);
        } else {
            addLog('error', 'UI', 'Process failed: ' + (data.errors || []).join(', '));
            renderError(data);
        }
        
        // Refresh queue count
        fetchQueue();
        
    } catch (e) {
        addLog('error', 'UI', 'Network error: ' + e.message);
    } finally {
        processBtn.disabled = false;
        indicator.classList.add('hidden');
    }
}

function renderPipeline(data) {
    // 1. Maker
    const stepMaker = document.getElementById('step-maker');
    const makerBody = stepMaker.querySelector('.step-body');
    stepMaker.querySelector('.step-status').textContent = 'Completed';
    stepMaker.querySelector('.step-status').className = 'step-status success';
    makerBody.classList.remove('hidden');
    
    if (data.maker_output) {
        document.getElementById('maker-confidence').textContent = (data.maker_output.confidence * 100).toFixed(1) + '%';
        document.getElementById('maker-reasoning').textContent = data.maker_output.reasoning;
        document.getElementById('maker-raw').textContent = JSON.stringify(data.maker_output, null, 2);
    }

    // 2. Validation
    const stepVal = document.getElementById('step-validation');
    stepVal.querySelector('.step-status').textContent = 'Passed';
    stepVal.querySelector('.step-status').className = 'step-status success';
    
    // 3. Checker
    const stepChecker = document.getElementById('step-checker');
    const checkerBody = stepChecker.querySelector('.step-body');
    const checkerDto = data.checker_result;
    
    if (checkerDto) {
        checkerBody.classList.remove('hidden');
        document.getElementById('checker-verdict').textContent = checkerDto.status.toUpperCase();
        document.getElementById('checker-summary').textContent = checkerDto.summary;
        
        const statusEl = stepChecker.querySelector('.step-status');
        statusEl.textContent = checkerDto.status;
        statusEl.className = 'step-status ' + (checkerDto.status === 'approved' ? 'success' : 'warn');
    }

    // 4. Final Entry
    const stepFinal = document.getElementById('step-final');
    stepFinal.querySelector('.step-body').classList.remove('hidden');
    renderJournalEntry(data.entry, data.db_entry_id);
}

function renderError(data) {
    alert("Processing Failed: " + JSON.stringify(data.errors));
}

function renderJournalEntry(entry, dbId) {
    if (!entry) return;
    
    const container = document.getElementById('journal-preview');
    let linesHtml = '';
    
    // Simple mock total
    let total = 0;
    
    entry.lines.forEach(line => {
        linesHtml += `
            <div class="journal-line">
                <span>${line.debit > 0 ? 'Dr. ' + line.account_name : '&nbsp;&nbsp;&nbsp;&nbsp;Cr. ' + line.account_name}</span>
                <span>${line.debit > 0 ? '₹' + line.debit : '₹' + line.credit}</span>
            </div>
        `;
        total += parseFloat(line.debit);
    });
    
    const contextHtml = `
        <div class="journal-header">
            <div><strong>${entry.transaction_date}</strong></div>
            <div>${entry.narration}</div>
        </div>
        ${linesHtml}
        <div class="journal-total">
            <span>TOTAL</span>
            <span>₹${total.toFixed(2)}</span>
        </div>
    `;
    
    container.innerHTML = contextHtml;
    
    // Bind actions
    document.getElementById('btn-approve').onclick = () => approveEntry(dbId);
    document.getElementById('btn-reject').onclick = () => rejectEntry(dbId);
}

async function approveEntry(id) {
    if(!id) return;
    if(!confirm("Approve this entry?")) return;
    
    await fetch(`/accounting/api/entries/${id}/approve/`, { method: 'POST' });
    alert("Approved!");
    fetchQueue();
}

async function rejectEntry(id) {
    if(!id) return;
    const reason = prompt("Reason for rejection:");
    if(!reason) return;
    
    await fetch(`/accounting/api/entries/${id}/reject/`, { 
        method: 'POST',
        body: JSON.stringify({ reason }) 
    });
    alert("Rejected!");
    fetchQueue();
}

async function fetchQueue() {
    try {
        const res = await fetch('/accounting/api/entries/');
        const data = await res.json();
        const tbody = document.querySelector('#review-table tbody');
        tbody.innerHTML = '';
        
        data.entries.forEach(entry => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${entry.date}</td>
                <td>${entry.narration.substring(0, 30)}...</td>
                <td>₹${entry.amount}</td>
                <td><span class="badge">${entry.status}</span></td>
                <td><button class="btn sm" onclick="loadEntry(${entry.id})">View</button></td>
            `;
            tbody.appendChild(row);
        });
        
        document.getElementById('queue-count').textContent = data.entries.length;
    } catch (e) {
        console.error("Failed to fetch queue", e);
    }
}

// Logs
async function pollLogs(sessionId) {
    const res = await fetch(`/accounting/api/logs/?session_id=${sessionId}`);
    const data = await res.json();
    
    const container = document.getElementById('logs-container');
    container.innerHTML = ''; // Re-render all for correct order
    
    data.logs.forEach(log => {
        const div = document.createElement('div');
        div.className = `log-entry ${log.level}`;
        const time = new Date(log.timestamp).toLocaleTimeString();
        div.innerHTML = `<span class="log-time">[${time}]</span> ${log.stage}: ${log.message}`;
        container.appendChild(div);
    });
}

function addLog(level, stage, message) {
    const container = document.getElementById('logs-container');
    const div = document.createElement('div');
    div.className = `log-entry ${level}`;
    const time = new Date().toLocaleTimeString();
    div.innerHTML = `<span class="log-time">[${time}]</span> ${stage}: ${message}`;
    container.prepend(div);
}

function loadEntry(id) {
    alert("Loading entry " + id + " details is not yet implemented fully on frontend, but backend API supports it.");
    // In full implementation, this would fetch entry details + logs and populate the pipeline view
}

// Helpers
window.fillExample = function(text) {
    document.getElementById('transaction-desc').value = text;
}

window.switchTab = function(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    
    if (tabName === 'pipeline') {
        document.querySelectorAll('.tab')[0].classList.add('active');
        document.getElementById('tab-pipeline').classList.add('active');
    } else {
        document.querySelectorAll('.tab')[1].classList.add('active');
        document.getElementById('tab-review').classList.add('active');
    }
}

window.clearPipeline = function() {
    document.querySelectorAll('.step-status').forEach(el => {
        el.textContent = 'Pending';
        el.className = 'step-status pending';
    });
    document.querySelectorAll('.step-body').forEach(el => el.classList.add('hidden'));
}

window.clearLogs = function() {
    document.getElementById('logs-container').innerHTML = '';
}
