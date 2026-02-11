// ml-client.js - Client-side ML handling using face-api.js
// REWRITTEN for proper 128D face embeddings

class MLClient {
    constructor() {
        this.isReady = false;
        // Point to the official models repo or a reliable mirror
        this.MODEL_URL = 'https://justadudewhohacks.github.io/face-api.js/models';
        this.minConfidence = 0.5;
        this.descriptorLength = 128;
    }

    async initialize(progressCallback) {
        try {
            console.log('Loading face-api.js models...');

            if (progressCallback) progressCallback({ progress: 10, message: 'Loading Face Detector...' });

            // Load models in parallel for speed
            await Promise.all([
                faceapi.nets.ssdMobilenetv1.loadFromUri(this.MODEL_URL), // Higher accuracy detector
                faceapi.nets.faceLandmark68Net.loadFromUri(this.MODEL_URL), // For face alignment
                faceapi.nets.faceRecognitionNet.loadFromUri(this.MODEL_URL) // For 128D embeddings
            ]);

            if (progressCallback) progressCallback({ progress: 100, message: 'Ready!' });

            this.isReady = true;
            console.log('✅ face-api.js models loaded successfully');
            return { success: true };

        } catch (error) {
            console.error('Model loading failed:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Detect faces in video stream
     * @param {HTMLVideoElement} videoElement
     */
    async detectFaces(videoElement) {
        if (!this.isReady) throw new Error('Models not loaded');

        // Use SSD MobileNet V1 for detection
        const detections = await faceapi.detectAllFaces(
            videoElement,
            new faceapi.SsdMobilenetv1Options({ minConfidence: this.minConfidence })
        ).withFaceLandmarks().withFaceDescriptors();

        return detections.map(det => ({
            box: {
                x: det.detection.box.x,
                y: det.detection.box.y,
                width: det.detection.box.width,
                height: det.detection.box.height
            },
            confidence: det.detection.score,
            // Include descriptor directly if needed, but for now we format to match old API
            descriptor: det.descriptor
        }));
    }

    /**
     * Generate embedding for a specific face (used in real-time recognition)
     * @param {HTMLVideoElement} videoElement 
     * @param {Object} faceBox - Not strictly needed if we re-detect, but we can optimise
     */
    async generateEmbedding(videoElement, faceBox) {
        if (!this.isReady) throw new Error('Models not loaded');

        // Note: In face-api, we usually do detection + embedding in one go.
        // If we are forced to separate, we can re-run detection on the region or full frame.
        // For efficiency in this specific API structure, we'll assume we want the best face close to the box 
        // OR we just detect all and find the matching one.

        // However, for best accuracy, we should run the full pipeline on the frame.
        const detections = await faceapi.detectAllFaces(
            videoElement,
            new faceapi.SsdMobilenetv1Options({ minConfidence: this.minConfidence })
        ).withFaceLandmarks().withFaceDescriptors();

        // Find the face closest to the provided box
        let bestMatch = null;
        let maxIoU = 0;

        for (const det of detections) {
            const iou = this.getIoU(faceBox, det.detection.box);
            if (iou > maxIoU) {
                maxIoU = iou;
                bestMatch = det;
            }
        }

        if (bestMatch && maxIoU > 0.3) {
            return Array.from(bestMatch.descriptor);
        }

        return null;
    }

    getIoU(box1, box2) {
        const x1 = Math.max(box1.x, box2.x);
        const y1 = Math.max(box1.y, box2.y);
        const x2 = Math.min(box1.x + box1.width, box2.x + box2.width);
        const y2 = Math.min(box1.y + box1.height, box2.y + box2.height);

        if (x1 >= x2 || y1 >= y2) return 0;

        const intersection = (x2 - x1) * (y2 - y1);
        const union = (box1.width * box1.height) + (box2.width * box2.height) - intersection;
        return intersection / union;
    }

    /**
     * Train from dataset
     * @param {Object} datasetInfo 
     * @param {Function} progressCallback 
     */
    async trainFromDataset(datasetInfo, progressCallback) {
        if (!this.isReady) throw new Error('Models not loaded');

        const results = [];
        const totalPersons = datasetInfo.persons.length;
        let processedPersons = 0;

        for (const person of datasetInfo.persons) {
            if (progressCallback) {
                progressCallback({
                    progress: Math.round((processedPersons / totalPersons) * 100),
                    message: `Processing ${person.name}...`,
                    person: person.name
                });
            }

            const personDescriptors = [];

            for (const imageEntry of person.images) {
                try {
                    let imageUrl = imageEntry.startsWith('http') ? imageEntry :
                        `${API_BASE_URL}${(datasetInfo.base_url || '').replace(/^\/api/, '')}/${encodeURIComponent(person.name)}/${imageEntry}`;

                    const img = await this.loadImage(imageUrl);

                    // Detect face and get descriptor (embedding)
                    const detection = await faceapi.detectSingleFace(
                        img,
                        new faceapi.SsdMobilenetv1Options({ minConfidence: this.minConfidence })
                    ).withFaceLandmarks().withFaceDescriptor();

                    if (detection) {
                        personDescriptors.push(detection.descriptor);
                    }
                } catch (error) {
                    console.warn(`Failed to process ${imageEntry}:`, error);
                }
            }

            if (personDescriptors.length > 0) {
                // Average the 128D vectors
                const avgDescriptor = this.averageVectors(personDescriptors);
                results.push({
                    name: person.name,
                    embedding: avgDescriptor
                });
            }
            processedPersons++;
        }

        if (progressCallback) {
            progressCallback({ progress: 100, message: `Training complete!` });
        }
        return results;
    }

    loadImage(url) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = () => resolve(img);
            img.onerror = reject;
            img.src = url;
        });
    }

    averageVectors(vectors) {
        const numVectors = vectors.length;
        const dims = vectors[0].length;
        const sum = new Float32Array(dims);

        for (const vec of vectors) {
            for (let i = 0; i < dims; i++) {
                sum[i] += vec[i];
            }
        }

        for (let i = 0; i < dims; i++) {
            sum[i] /= numVectors;
        }

        return Array.from(sum);
    }

    cleanup() {
        this.isReady = false;
        // face-api doesn't have a strict dispose like TFJS layers model
    }
}

window.MLClient = MLClient;