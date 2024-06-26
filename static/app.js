function onScanSuccess(decodedText, decodedResult) {
    console.log(`Code scanned = ${decodedText}`, decodedResult);
    const data = decodedText.split(', ');
    document.getElementById('batch_number').value = data[0].split(': ')[1];
    document.getElementById('part_number').value = data[1].split(': ')[1];
    document.getElementById('quantity').value = data[2].split(': ')[1];
}

const html5QrcodeScanner = new Html5QrcodeScanner(
    "reader", { fps: 10, qrbox: 250 }
);
html5QrcodeScanner.render(onScanSuccess);
