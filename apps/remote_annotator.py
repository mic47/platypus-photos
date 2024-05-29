import datetime
import traceback
import sys

from fastapi import FastAPI

from annots.text import AnnotateRequest, Models, ImageClassification
from data_model.features import WithImage
from db.cache import NoCache

MODELS = Models(NoCache(), None)

app = FastAPI()


@app.post(
    "/annotate/image_to_text",
    response_model=ImageClassification,
)
def image_endpoint(image: AnnotateRequest) -> WithImage[ImageClassification]:
    now = datetime.datetime.now()
    try:
        ret = MODELS.process_image_data(image)
    # pylint: disable = bare-except
    except:
        ret = WithImage(
            image.path,
            ImageClassification.current_version(),
            ImageClassification([], [], traceback.format_exc()),
        )
        traceback.print_exc()
        print("Error processing file:", image.path, file=sys.stderr)
    after = datetime.datetime.now()
    print(after - now)
    return ret
