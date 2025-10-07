
from ultralytics import YOLO
import io
from PIL import Image


def model_server(server_req_q, server_resp_q, model_path):
    """
    Run a YOLO model server process for document layout detection.

    This function is designed to run as a background worker in a separate process.
    It continuously listens for incoming OCR/layout requests via a multiprocessing
    queue, performs inference using a YOLO model, and sends the results back through
    a response queue.

    Workflow:
        1. Wait for an incoming job tuple: (job_id, page_png_bytes)
        2. Load the PNG bytes into a PIL Image
        3. Perform layout detection using a YOLO model
        4. Put the (job_id, results) tuple back into the response queue
        5. Exit cleanly when a `None` job is received

    Args:
        server_req_q (multiprocessing.Queue):
            Queue from which to receive incoming page jobs. Each job is expected
            to be a tuple `(job_id: int, page_png_bytes: bytes)`.
        server_resp_q (multiprocessing.Queue):
            Queue through which inference results will be sent back.
        model_path (str):
            Path to the YOLO model file (e.g., "models/yolov8n-doclaynet.pt").

    Example:
        ```python
        from multiprocessing import Process, Manager
        from src.modules.model_server import model_server

        manager = Manager()
        req_q = manager.Queue()
        resp_q = manager.Queue()

        server = Process(target=model_server, args=(req_q, resp_q, "models/yolo-layout.pt"))
        server.start()

        # Send a sample image job
        req_q.put((1, open("page.png", "rb").read()))

        # Get results
        job_id, result = resp_q.get()
        print(job_id, result)

        # Shut down gracefully
        req_q.put(None)
        server.join()
        ```
    """
    
   
    model = YOLO(model_path)


    while True:
        job = server_req_q.get()
        
        if job is None :
            break

        job_id, page_png_bytes = job


        img = Image.open(io.BytesIO(page_png_bytes))
        results = model.predict(source=img, imgsz=640, verbose=False)

        server_resp_q.put((job_id, results))
