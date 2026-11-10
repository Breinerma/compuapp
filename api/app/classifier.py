from io import BytesIO
from pathlib import Path
from threading import Lock
from time import perf_counter
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 25_000_000

def prepare_photo(raw):
    try:
        with Image.open(BytesIO(raw)) as source:
            if source.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise ValueError('Usa una foto JPG, PNG o WebP.')
            if source.width * source.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError('La foto supera los 25 megapíxeles.')
            image = ImageOps.exif_transpose(source).convert('RGB')
            tensor = np.asarray(image.resize((224, 224), Image.Resampling.BILINEAR), dtype=np.float32)[None, ...]
            image.thumbnail((1600, 1600))
            output = BytesIO()
            image.save(output, 'JPEG', quality=90)
            return tensor, output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('No se pudo leer la foto. Usa una imagen válida de hasta 25 megapíxeles.') from exc

class Classifier:
    def __init__(self):
        from tensorflow.lite.python.interpreter import Interpreter
        root = Path(__file__).resolve().parent.parent / 'model'
        self.labels = [line.strip() for line in (root / 'labels.txt').read_text(encoding='utf-8').splitlines() if line.strip()]
        self.interpreter = Interpreter(model_path=str(root / 'mamiferos_tolima_dinamico.tflite'), num_threads=2)
        self.interpreter.allocate_tensors()
        self.input = self.interpreter.get_input_details()[0]
        self.output = self.interpreter.get_output_details()[0]
        if list(self.input['shape']) != [1, 224, 224, 3] or self.input['dtype'] != np.float32:
            raise RuntimeError('El modelo debe recibir float32 [1,224,224,3], RGB 0–255.')
        if self.output['shape'][-1] != len(self.labels):
            raise RuntimeError('Las etiquetas no coinciden con las salidas del modelo.')
        self.lock = Lock()

    def predict(self, tensor):
        with self.lock:
            start = perf_counter()
            self.interpreter.set_tensor(self.input['index'], tensor)
            self.interpreter.invoke()
            probs = self.interpreter.get_tensor(self.output['index'])[0].copy()
            elapsed = round((perf_counter() - start) * 1000)
        top = np.argsort(probs)[::-1][:3]
        return [{'species': self.labels[i].replace('-', ' ').replace('_', ' '), 'confidence': float(probs[i])} for i in top], elapsed
