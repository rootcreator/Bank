import requests
import pytesseract
from PIL import Image
from deepface import DeepFace


def extract_text_from_image(image_path):
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)
    return text


def verify_id(id_document, selfie):
    # Call an external API or use a custom algorithm
    response = requests.post('https://api.idverification.com/verify', files={'document': id_document, 'selfie': selfie})
    return response.json().get('verified', False)


def verify_address(address_document):
    # Call an address verification service or manually check
    response = requests.post('https://api.addressverification.com/verify', files={'document': address_document})
    return response.json().get('verified', False)


def run_aml_check(user):
    # Query against AML database or external service
    response = requests.post('https://api.amlcheck.com/check', json={'name': user.get_full_name()})
    return response.json().get('cleared', False)


def verify_faces(id_photo, selfie):
    id_image = DeepFace.load_image_file(id_photo)
    selfie_image = DeepFace.load_image_file(selfie)
    id_encoding = DeepFace.face_encodings(id_image)[0]
    selfie_encoding = DeepFace.face_encodings(selfie)[0]

    results = DeepFace.verify([id_encoding], selfie_encoding)
    return results['verified']


def send_approval_notification(user):
    # Notify the user via email
    user.email_user('KYC Approved', 'Your KYC has been successfully verified.')
