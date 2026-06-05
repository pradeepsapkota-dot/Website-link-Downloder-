// ── FAQ toggle ──────────────────────────────────────
function toggleFaq(i) {
    const answer = document.getElementById('faq' + i);
    answer.classList.toggle('open');
}

// ── Status helper ───────────────────────────────────
function showStatus(msg, type) {
    const s = document.getElementById('status');
    s.textContent = msg;
    s.className = 'status ' + type;
}

// ── Download handler ────────────────────────────────
async function startDownload() {
    const url = document.getElementById('urlInput').value.trim();
    const quality = document.getElementById('qualitySelect').value;
    const btn = document.getElementById('dlBtn');

    if (!url) {
        showStatus('Please paste a link first!', 'error');
        return;
    }
    if (!url.startsWith('http')) {
        showStatus('Please enter a valid URL starting with http.', 'error');
        return;
    }

    btn.disabled = true;
    showStatus('Connecting... please wait', 'loading');

    try {
        const response = await fetch('/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, quality })
        });

        const data = await response.json();

        if (!response.ok || data.error) {
            showStatus('Error: ' + data.error, 'error');
            return;
        }

        if (!data.download_url) {
            showStatus('Error: No download URL returned.', 'error');
            return;
        }

        // Open in new tab — browser handles download
        window.open(data.download_url, '_blank');
        showStatus('Download started successfully!', 'success');

    } catch (e) {
        showStatus('Something went wrong. Try again.', 'error');
    } finally {
        btn.disabled = false;
    }
}
// ── Allow pressing Enter to download ───────────────
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('urlInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') startDownload();
    });
});