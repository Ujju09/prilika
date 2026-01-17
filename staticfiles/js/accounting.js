// CSRF Token Helper
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Get CSRF token for POST requests
function getCSRFToken() {
    return getCookie('csrftoken');
}

document.addEventListener('DOMContentLoaded', () => {
    // Set default date to today
    document.getElementById('transaction-date').valueAsDate = new Date();

    // Event Listeners
    document.getElementById('process-btn').addEventListener('click', processTransaction);
});

async function processTransaction() {
    const descInput = document.getElementById('transaction-desc');
    const dateInput = document.getElementById('transaction-date');
    const processBtn = document.getElementById('process-btn');
    const statusInd = document.getElementById('status-indicator');
    
    const description = descInput.value.trim();
    if (!description) {
        // Minimal shake effect or focus
        descInput.focus();
        return;
    }
    
    // UI State: Running
    processBtn.disabled = true;
    statusInd.classList.remove('hidden');
    clearFeed();
    
    // Add "Processing" start node
    addFeedItem('system', { message: 'Transaction processing started...' });
    
    try {
        const headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()  // Add CSRF token for security
        };

        // Simulate "thinking" time for better UX if it's too fast,
        // or just let it fly.

        const response = await fetch('/accounting/api/process/', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                description: description,
                date: dateInput.value
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Render the flow sequentially
            if (data.maker_output) {
                await delay(300);
                addFeedItem('maker', data.maker_output);
            }
            
            // Validation is implicit in the success usually, but if there are warnings:
            // if (data.validation_errors) ...

            if (data.checker_result) {
                await delay(300);
                addFeedItem('checker', data.checker_result);
            }

            if (data.entry) {
                await delay(300);
                addFeedItem('journal', { entry: data.entry, dbId: data.db_entry_id });
            }
            
            statusInd.textContent = 'Complete';
            
        } else {
            addFeedItem('error', { errors: data.errors });
            statusInd.textContent = 'Failed';
        }
        
    } catch (e) {
        addFeedItem('error', { errors: [e.message] });
        statusInd.textContent = 'Error';
    } finally {
        processBtn.disabled = false;
        setTimeout(() => statusInd.classList.add('hidden'), 2000);
    }
}

function clearFeed() {
    document.getElementById('processing-feed').innerHTML = '';
}

function addFeedItem(type, data) {
    const container = document.getElementById('processing-feed');
    const item = document.createElement('div');
    item.className = 'feed-item active';
    
    let label = type.toUpperCase();
    let contentHtml = '';
    let tagClass = type; // matches css .tag.maker etc
    
    if (type === 'maker') {
        const conf = (data.confidence * 100).toFixed(0);
        contentHtml = `
            <div class="reasoning-text">${data.reasoning}</div>
            <div class="kv-grid">
                <span class="kv-label">Confidence</span>
                <span class="text-secondary">${conf}%</span>
            </div>
        `;
    } else if (type === 'checker') {
        contentHtml = `
            <div class="reasoning-text">${data.summary}</div>
            <div class="kv-grid">
                <span class="kv-label">Verdict</span>
                <span class="${data.status === 'approved' ? 'text-primary' : 'text-danger'}">${data.status.toUpperCase()}</span>
            </div>
        `;
    } else if (type === 'journal') {
        label = "JOURNAL ENTRY PROPOSAL";
        tagClass = 'system'; // or special journal style
        
        const ent = data.entry;
        let rows = '';
        let total = 0;
        
        ent.lines.forEach(line => {
            const isDr = line.debit > 0;
            rows += `
                <tr>
                    <td>
                        <div class="${!isDr ? 'indent' : ''}">
                            ${isDr ? line.account_name : 'To ' + line.account_name}
                        </div>
                    </td>
                    <td class="col-dr">${isDr ? '₹' + line.debit : ''}</td>
                    <td class="col-cr">${!isDr ? '₹' + line.credit : ''}</td>
                </tr>
            `;
            total += parseFloat(line.debit);
        });
        
        contentHtml = `
            <div class="text-secondary text-sm" style="margin-bottom: 8px;">
                ${ent.transaction_date} • ${ent.narration}
            </div>
            <table class="journal-table">
                ${rows}
            </table>
            <div class="amount-total">
                <span>Total</span>
                <span>₹${total.toFixed(2)}</span>
            </div>
            
            <div class="action-bar" id="actions-${data.dbId}">
                <button class="btn btn-approve" onclick="approveEntry(${data.dbId})">Approve & Post</button>
                <button class="btn btn-reject" onclick="rejectEntry(${data.dbId})">Reject</button>
            </div>
        `;
    } else if (type === 'error') {
        item.className += ' error';
        const errorList = data.errors || ['An unknown error occurred'];
        contentHtml = `<div style="color: var(--danger)">${errorList.join('<br>')}</div>`;
    } else if (type === 'system') {
        contentHtml = `<div class="text-secondary">${data.message}</div>`;
    }

    item.innerHTML = `
        <div class="feed-header">
            <span class="tag ${tagClass}">${label}</span>
        </div>
        <div class="feed-content">
            ${contentHtml}
        </div>
    `;
    
    container.appendChild(item);
    item.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

async function approveEntry(id) {
    if(!id) return;
    const actionsDiv = document.getElementById(`actions-${id}`);

    // Optimistic UI
    actionsDiv.innerHTML = '<span class="text-secondary">Posting...</span>';

    try {
        await fetch(`/accounting/api/entries/${id}/approve/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken()  // Add CSRF token
            }
        });
        actionsDiv.innerHTML = '<span style="color: var(--success)">✓ Approved & Posted</span>';
    } catch(e) {
        alert("Error approving: " + e.message);
        // Restore buttons (simplified for now)
    }
}

async function rejectEntry(id) {
    if(!id) return;
    const reason = prompt("Reason for rejection:");
    if(!reason) return;

    const actionsDiv = document.getElementById(`actions-${id}`);
    actionsDiv.innerHTML = '<span class="text-secondary">Rejecting...</span>';

    try {
        await fetch(`/accounting/api/entries/${id}/reject/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()  // Add CSRF token
            },
            body: JSON.stringify({ reason })
        });
        actionsDiv.innerHTML = '<span style="color: var(--danger)">✗ Rejected</span>';
    } catch(e) {
        alert("Error rejecting: " + e.message);
    }
}

// Helpers
window.fillExample = function(text) {
    document.getElementById('transaction-desc').value = text;
    document.getElementById('transaction-desc').focus();
}

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
