import os
import io
from flask import Flask, render_template, request, jsonify
import cv2
from skimage.metrics import structural_similarity as ssim
from PIL import Image, ImageChops, ImageEnhance
import numpy as np
import tempfile
import requests  # For downloading image from URL

app = Flask(__name__)

# Configure upload and result folders
UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = os.path.join('static', 'resullsts')  # Store results in static for easy access
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULT_FOLDER'] = RESULT_FOLDER

def save_upload(file, filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    return file_path

def save_result(image, filename):
    result_image_path = os.path.join(app.config['RESULT_FOLDER'], filename)
    cv2.imwrite(result_image_path, image)
    return os.path.join('results', filename)  # Return relative path for Flask serving

def determine_jpeg_quality(image):
    """
    Determines an adaptive JPEG quality based on image characteristics.
    """
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    variance = gray_image.var()

    if variance < 500:  # Low detail images
        return 50  # Lower quality for less detail
    elif variance < 1500:  # Medium detail images
        return 70  # Medium quality for average detail
    else:
        return 90  # High quality for detailed images

def create_ela_image(original_image_path, filename="ela_img.jpg"):
    """
    Produces an enhanced Error Level Analysis image with a specified filename.
    """
    try:
        im = Image.open(original_image_path).convert('RGB')
        temp_filename = "temp_resaved.jpg"
        temp_resaved_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)

        # Determine adaptive JPEG quality based on image characteristics
        img_cv = cv2.imread(original_image_path)
        jpeg_quality = determine_jpeg_quality(img_cv)

        im.save(temp_resaved_path, 'JPEG', quality=jpeg_quality)

        resaved_im = Image.open(temp_resaved_path)
        ela_im = ImageChops.difference(im, resaved_im)

        # Convert to numpy array for further processing
        ela_np = np.array(ela_im)

        # Split into color channels
        b_channel, g_channel, r_channel = cv2.split(ela_np)

        # Apply CLAHE to each channel
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        b_clahe = clahe.apply(b_channel)
        g_clahe = clahe.apply(g_channel)
        r_clahe = clahe.apply(r_channel)

        # Merge channels back
        ela_clahe = cv2.merge((b_clahe, g_clahe, r_clahe))

        # Sharpening using a kernel
        kernel = np.array([[0, -1, 0],
                           [-1, 5,-1],
                           [0, -1, 0]])
        sharpened_ela = cv2.filter2D(ela_clahe, -1, kernel)

        # Convert back to PIL Image for brightness adjustment
        enhanced_ela_image = Image.fromarray(sharpened_ela)

        # Reduce brightness (adjust factor as needed)
        enhancer = ImageEnhance.Brightness(enhanced_ela_image)
        enhanced_ela_image = enhancer.enhance(1.3)  # Adjusted brightness

        # Convert to BGR for OpenCV operations
        ela_cv = cv2.cvtColor(np.array(enhanced_ela_image), cv2.COLOR_RGB2BGR)

        # Convert to grayscale
        gray = cv2.cvtColor(ela_cv, cv2.COLOR_BGR2GRAY)

        # Apply threshold to highlight manipulated regions (lowered threshold for better detection)
        _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)  # Adjusted threshold

        # Highlight edits in red
        ela_cv[thresh == 255] = [0, 0, 255]

        # Apply additional sharpening if needed
        kernel_sharp = np.array([[0, -1, 0],
                                 [-1, 5,-1],
                                 [0, -1, 0]])
        ela_cv_sharp = cv2.filter2D(ela_cv, -1, kernel_sharp)

        ela_path = os.path.join(app.config['RESULT_FOLDER'], filename)

        # Save the final enhanced ELA image as color
        cv2.imwrite(ela_path, ela_cv_sharp)

        os.remove(temp_resaved_path)  # Clean up temporary file
        return os.path.join('results', filename)

    except Exception as e:
        print(f"Error during ELA: {e}")
        return None

def compare_images(img1_path, img2_path):
    img1 = cv2.imread(img1_path, cv2.IMREAD_COLOR)
    img2 = cv2.imread(img2_path, cv2.IMREAD_COLOR)

    height, width = img1.shape[:2]
    img2 = cv2.resize(img2, (width, height))

    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

    # Calculate the absolute difference between the images
    diff = cv2.absdiff(gray1, gray2)
    total_difference = np.sum(diff)

    # Define a threshold for "no difference" (adjust as needed)
    no_difference_threshold = 100  # Example threshold

    if total_difference <= no_difference_threshold:
        # Images are considered identical
        score = 1.0
        diff = np.zeros_like(gray1, dtype=np.uint8)  # No difference, so black image
    else:
        # Images are different
        score, diff_img = ssim(gray1, gray2, full=True)
        # Scale the SSIM score to be below 0.9 based on the difference
        score = min(0.9, score)  # Ensure score is capped at 0.9
        # Further adjust score based on the amount of difference
        score = score * (1 - (total_difference / (gray1.size * 255)))  # Scale the score based on the difference
        diff = (diff_img * 255).astype("uint8")  # convert to image

    diff_colored = cv2.applyColorMap(diff, cv2.COLORMAP_JET)
    ssim_diff_filename = "ssim_diff.jpg"
    diff_path = save_result(diff_colored, ssim_diff_filename)

    # Create ELA images for both input images using the same method as in analyze_image
    ela_img1_filename = "ela_img1.jpg"
    ela_img2_filename = "ela_img2.jpg"
    ela_img1_path = create_ela_image(img1_path, filename=ela_img1_filename)
    ela_img2_path = create_ela_image(img2_path, filename=ela_img2_filename)

    return {
        "ssim_score": score,
        "ssim_diff": diff_path,
        "ela_img1": ela_img1_path,
        "ela_img2": ela_img2_path
    }

def analyze_image(image_path):
    """Analyzes the image and returns the path to the enhanced ELA image."""
    ela_image_path = create_ela_image(image_path, filename="ela_img.jpg")
    return {"ela_img": ela_image_path}

@app.route("/image-to-image", methods=["POST"])
def image_to_image():
    img1 = request.files["img1"]
    img2 = request.files["img2"]

    img1_path = save_upload(img1, img1.filename)
    img2_path = save_upload(img2, img2.filename)

    result = compare_images(img1_path, img2_path)

    return render_template('result.html', **result, section="image-to-image")

@app.route("/image-analysis", methods=["POST"])
def image_analysis():
    img = request.files["single_img"]
    img_path = save_upload(img, img.filename)

    # Perform ELA and get the path to the ELA image
    ela_result = analyze_image(img_path)

    # Pass the ELA image path to the template
    return render_template('result.html', ela_img=ela_result["ela_img"], section="image-analysis")

@app.route("/image-url-analysis", methods=["POST"])
def image_url_analysis():
    try:
        image_url = request.form["image_url"]
        response = requests.get(image_url, stream=True)
        response.raise_for_status()  # Raise HTTPError for bad responses (4XX, 5XX)

        image = Image.open(io.BytesIO(response.content))

        # Generate a unique filename for the downloaded image
        filename = "url_image_" + str(hash(image_url)) + ".jpg"
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(image_path)

        # Perform ELA analysis
        ela_result = analyze_image(image_path)

        return render_template('result.html', ela_img=ela_result["ela_img"], section="image-url-analysis")

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error downloading image from URL: {e}"})
    except Exception as e:
        return jsonify({"error": f"Error processing image: {e}"})

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
