if __name__ == "__main__":
    # pylint: disable-next = import-outside-toplevel,import-error,unused-import
    import transformers  # noqa: F401

    # pylint: disable-next = import-outside-toplevel,import-error
    from transformers import pipeline

    pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
    import ultralytics
    for model in ["yolov8x.pt", "yolov8x-cls.pt"]:
        ultralytics.YOLO(model)
