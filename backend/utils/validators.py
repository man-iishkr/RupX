import os

def validate_dataset_structure(dataset_path: str, min_images: int = 10):
    if not os.path.isdir(dataset_path):
        raise ValueError("Dataset path invalid")

    persons = [p for p in os.listdir(dataset_path) if os.path.isdir(os.path.join(dataset_path, p))]
    if not persons:
        raise ValueError("No person folders found")

    for person in persons:
        imgs = os.listdir(os.path.join(dataset_path, person))
        valid_imgs = [i for i in imgs if i.lower().endswith((".jpg", ".jpeg", ".png"))]
        if len(valid_imgs) < min_images:
            raise ValueError(f"{person} has less than {min_images} images")
