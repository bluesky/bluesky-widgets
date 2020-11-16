def generate_thumbnail(run):
    """
    Return one thumbnail image to represent a Run if any image-like data can be found.

    Logs details to the stderr.

    Parameters
    ----------
    run: BlueskyRun

    Returns
    -------
    image: np.array, None
    """

    uid = run.metadata["start"]["uid"]
    if "primary" in run:
        stream_name = "primary"
    elif list(run):
        # Just grab the first stream.
        stream_name = list(run)[0]
    else:
        print(f"No image data found in Run {uid:.8}")
    dataset = run[stream_name].to_dask()

    # Find the first column that looks like an image.
    # Grab a slice from the middle because that is most likely to be interesting.
    for column in dataset:
        xarr = dataset[column]
        if xarr.ndim == 3:  # a column of single images
            image = dataset[column][xarr.shape[0] // 2]
            break
        elif xarr.ndim == 4:  # a column of stacks of images (like Area Detector gives)
            image = dataset[column][xarr.shape[0] // 2, xarr.shape[1] // 2]
            break
    else:
        print(f"No image data found in Run {uid:.8}")
        return None

    print(f"Found {column!r} from Run {uid}")
    return image
