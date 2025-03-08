// Function to handle the form submission based on section (image-to-image, image analysis, deepfake testing)
async function handleSubmit(event, section) {
  event.preventDefault(); 

  const formData = new FormData(event.target); // Get the form data
  let response;
  let result;

  try {
      if (section === "image-to-image") {
          response = await fetch('/image-to-image', {
              method: 'POST',
              body: formData
          });
          result = await response.json(); // Expecting a JSON response

          // Update results on result page (SSIM diff, ELA images)
          if (result.ssim_diff) updateImageSrc('ssim-diff', result.ssim_diff, 'SSIM Difference Image');
          if (result.ela_img1) updateImageSrc('ela-img1', result.ela_img1, 'ELA Image 1');
          if (result.ela_img2) updateImageSrc('ela-img2', result.ela_img2, 'ELA Image 2');

          // Display SSIM score
          if (result.ssim_score) {
              document.getElementById('ssim-score').textContent = `SSIM Score: ${result.ssim_score}`;
          }
      } else if (section === "image-analysis") {
          response = await fetch('/image-analysis', {
              method: 'POST',
              body: formData
          });
          result = await response.json(); 

          if (result.ela_img) updateImageSrc('ela-image', result.ela_img, 'ELA Image');
      } else if (section === "deepfake") {
          response = await fetch('/deepfake', {
              method: 'POST',
              body: formData
          });
          result = await response.json(); 

          if (result.label) {
              alert(`Deepfake Result: ${result.label} (Confidence: ${result.confidence})`);
          } else if (result.forged_frames) {
              setupSlider(result.forged_frames); 
          } else {
              alert('Error: Unsupported file format or an issue with the media.');
          }
      }
  } catch (error) {
      alert('Error processing the form submission. Please try again.');
      console.error("Submission Error:", error); 
  }
}

// Function to update image source dynamically and add a label below the image
function updateImageSrc(elementId, imagePath, labelText) {
  const imgElement = document.getElementById(elementId);
  if (imgElement) {
      imgElement.src = `/static/${imagePath}`;
      
      // Add the label under the image
      const labelElement = document.getElementById(`${elementId}-label`);
      if (labelElement) {
          labelElement.textContent = labelText;
      }
  }
}

// Function to setup the deepfake video frame slider
function setupSlider(framePaths) {
  const sliderContainer = document.querySelector('.image-slider .slides');
  sliderContainer.innerHTML = ''; 
  
  framePaths.forEach(frame => {
      const figure = document.createElement('figure');
      const img = document.createElement('img');
      img.src = `/static/${frame}`; 
      img.alt = 'Forged Frame';
      
      const caption = document.createElement('figcaption');
      caption.textContent = 'Forged Frame';
      
      figure.appendChild(img);
      figure.appendChild(caption);
      sliderContainer.appendChild(figure);
  });

  // Show slider if frames are added
  document.querySelector('.image-slider').style.display = 'block';

  // Initialize the slider by showing the first slide
  currentSlide = 0;
  showSlide(currentSlide);
}

let currentSlide = 0;

function showSlide(index) {
  const slides = document.querySelectorAll('.slides figure');
  
  // Loop back to first slide if at the end
  if (index >= slides.length) {
      currentSlide = 0; 
  } else if (index < 0) {
      currentSlide = slides.length - 1; 
  } else {
      currentSlide = index;
  }
  
  const offset = -currentSlide * 100; // Calculate offset for sliding effect
  document.querySelector('.slides').style.transform = `translateX(${offset}%)`;
}

function changeSlide(direction) {
  showSlide(currentSlide + direction);
}

// Function to handle back button click event
function goBack() {
  window.location.href = '/'; 
}

// Event listeners for navigation buttons in the slider
document.addEventListener('DOMContentLoaded', () => {
  const prevButton = document.querySelector('.prev');
  const nextButton = document.querySelector('.next');

  if (prevButton && nextButton) {
      prevButton.addEventListener('click', () => changeSlide(-1));
      nextButton.addEventListener('click', () => changeSlide(1));
  }
});
