import datetime
import traceback

from fastapi import FastAPI

from image_to_text import AnnotateRequest, Models, ImageClassification
from cache import NoCache

MODELS = Models(NoCache(), None)

app = FastAPI()


@app.post(
    "/annotate/image_to_text",
    response_model=ImageClassification,
)
def image_endpoint(image: AnnotateRequest) -> ImageClassification:
    now = datetime.datetime.now()
    try:
        ret = MODELS.process_image_data(image)
    # pylint: disable = bare-except
    except:
        ret = ImageClassification(
            image.path, ImageClassification.current_version(), [], [], traceback.format_exc()
        )
        traceback.print_exc()
    after = datetime.datetime.now()
    print(after - now)
    return ret
