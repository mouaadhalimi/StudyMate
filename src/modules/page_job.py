
import io
from typing import Any, Dict, List, Tuple
import pytesseract
from PIL import Image
import uuid


def page_job(args: Tuple[int, bytes, str, Any, Any]) -> List[Dict]:
    """
    Process a single document page for layout detection and OCR text extraction.

    This function serves as the atomic processing unit for document layout extraction.
    It sends an image of a document page to a YOLO-based model server to detect
    layout elements (e.g., text, titles, tables), and then performs OCR on each
    detected region using Tesseract.

    Workflow:
        1. Send the page image bytes to the model server via the request queue.
        2. Wait for the server response using a unique job ID.
        3. For each detected bounding box:
            - Crop the corresponding image region.
            - Run OCR (Optical Character Recognition) on it.
            - Collect structured text block data.
        4. Return all extracted text blocks in a sorted list.

    Args:
        args (Tuple[int, bytes, str, Any, Any]):
            A tuple containing:
                - page_number (int): Page index in the document.
                - page_png_bytes (bytes): PNG image data of the page.
                - ocr_lang (str): OCR language code for Tesseract (e.g., "eng", "fra").
                - server_req_q (multiprocessing.Queue): Queue used to send page jobs to the model server.
                - server_resp_q (multiprocessing.Queue): Queue used to receive inference results.

    Returns:
        List[Dict]: A list of structured OCR block dictionaries, where each entry includes:
            - "type" (str): The detected block type label (e.g., "text", "title", "table").
            - "text" (str): The recognized text content.
            - "page" (int): The page number the block belongs to.
            - "y" (float): The top Y-coordinate position of the block in the page.

    Raises:
        RuntimeError: If `server_req_q` or `server_resp_q` are not provided.
        TimeoutError: If the model server does not respond within 30 seconds.
    """
    page_number, page_png_bytes, ocr_lang, server_req_q, server_resp_q = args

    if server_req_q is None or server_resp_q is None:

        raise RuntimeError("server_req_q or server_resp_q were not provided to page_job!")

    job_id = str(uuid.uuid4())

    server_req_q.put((job_id, page_png_bytes))

    while True:
        jid, results = server_resp_q.get(timeout=30)
        if jid == job_id:  
            break
        else:

            server_resp_q.put((jid, results))

    img = Image.open(io.BytesIO(page_png_bytes))
    blocks = []
    for r in results[0].boxes:
        cls_id = int(r.cls.item())
        label = results[0].names[cls_id]
        x1, y1, x2, y2 = map(int, r.xyxy[0].tolist())
        cropped = img.crop((x1, y1, x2, y2))
        text = pytesseract.image_to_string(cropped, lang=ocr_lang).strip()

        if text:
            blocks.append({
                "type": label.lower(),
                "text": text,
                "page": page_number,
                "y": float(y1)
            })
    return blocks

