/**
 * ml-client.js
 * TensorFlow.js wrapper for browser-based face recognition
 * Place this in: frontend/dashboard/ml-client.js
 */

class MLClient {
    constructor() {
        this.faceDetector = null;
        this.faceNetModel = null;
        this.isReady = false;
    }

    async initialize(progressCallback) {
        try {
            console.log('🔄 Loading TensorFlow.js models...');
            
            if (progressCallback) progressCallback({ progress: 20, message: 'Loading face detector...' });
            this.faceDetector = await blazeface.load();
            
            if (progressCallback) progressCallback({ progress: 60, message: 'Loading recognition model...' });
            await this.loadEmbeddingModel();
            
            if (progressCallback) progressCallback({ progress: 100, message: 'Ready!' });
            
            this.isReady = true;
            console.log('✅ Models loaded successfully');
            return { success: true };
            
        } catch (error) {
            console.error('❌ Model loading failed:', error);
            return { success: false, error: error.message };
        }
    }

    async loadEmbeddingModel() {
        const MODEL_URL = 'https://storage.googleapis.com/tfjs-models/tfjs/mobilenet_v1_0.25_224/model.json';
        this.faceNetModel = await tf.loadLayersModel(MODEL_URL);
        
        // Warm up model
        const dummy = tf.zeros([1, 224, 224, 3]);
        this.faceNetModel.predict(dummy).dispose();
        dummy.dispose();
    }

    async detectFaces(videoElement) {
        if (!this.isReady) throw new Error('Models not loaded');
        
        const predictions = await this.faceDetector.estimateFaces(videoElement, false);
        
        return predictions.map(pred => ({
            box: {
                x: pred.topLeft[0],
                y: pred.topLeft[1],
                width: pred.bottomRight[0] - pred.topLeft[0],
                height: pred.bottomRight[1] - pred.topLeft[1]
            },
            confidence: pred.probability
        }));
    }

    async generateEmbedding(videoElement, faceBox) {
        if (!this.isReady) throw new Error('Models not loaded');

        return tf.tidy(() => {
            const video = tf.browser.fromPixels(videoElement);
            const cropped = tf.image.cropAndResize(
                video.expandDims(0),
                [[
                    faceBox.y / videoElement.videoHeight,
                    faceBox.x / videoElement.videoWidth,
                    (faceBox.y + faceBox.height) / videoElement.videoHeight,
                    (faceBox.x + faceBox.width) / videoElement.videoWidth
                ]],
                [0],
                [224, 224]
            );
            
            const normalized = cropped.div(127.5).sub(1.0);
            const embedding = this.faceNetModel.predict(normalized);
            const reshaped = embedding.reshape([224]);
            
            // Pad to 512 dimensions
            let embedding512;
            if (reshaped.shape[0] < 512) {
                const padding = tf.zeros([512 - reshaped.shape[0]]);
                embedding512 = tf.concat([reshaped, padding]);
            } else {
                embedding512 = reshaped.slice([0], [512]);
            }
            
            const embArray = Array.from(embedding512.dataSync());
            const norm = Math.sqrt(embArray.reduce((sum, val) => sum + val * val, 0));
            return embArray.map(val => val / norm);
        });
    }

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

            const personEmbeddings = [];

            for (const imageName of person.images) {
                try {
                    const imageUrl = `${API_BASE_URL}${datasetInfo.base_url}/${encodeURIComponent(person.name)}/${imageName}`;
                    const img = await this.loadImage(imageUrl);
                    const faces = await this.detectFacesInImage(img);
                    
                    if (faces.length > 0) {
                        const embedding = await this.generateEmbeddingFromImage(img, faces[0].box);
                        personEmbeddings.push(embedding);
                    }
                } catch (error) {
                    console.warn(`Failed to process ${imageName}:`, error);
                }
            }

            if (personEmbeddings.length > 0) {
                const avgEmbedding = this.averageEmbeddings(personEmbeddings);
                results.push({
                    name: person.name,
                    embedding: avgEmbedding
                });
            }

            processedPersons++;
        }

        if (progressCallback) {
            progressCallback({
                progress: 100,
                message: `Training complete! Processed ${results.length} persons.`
            });
        }

        return results;
    }

    async detectFacesInImage(img) {
        const predictions = await this.faceDetector.estimateFaces(img, false);
        return predictions.map(pred => ({
            box: {
                x: pred.topLeft[0],
                y: pred.topLeft[1],
                width: pred.bottomRight[0] - pred.topLeft[0],
                height: pred.bottomRight[1] - pred.topLeft[1]
            }
        }));
    }

    async generateEmbeddingFromImage(img, faceBox) {
        return tf.tidy(() => {
            const imgTensor = tf.browser.fromPixels(img);
            const cropped = tf.image.cropAndResize(
                imgTensor.expandDims(0),
                [[
                    faceBox.y / img.height,
                    faceBox.x / img.width,
                    (faceBox.y + faceBox.height) / img.height,
                    (faceBox.x + faceBox.width) / img.width
                ]],
                [0],
                [224, 224]
            );
            
            const normalized = cropped.div(127.5).sub(1.0);
            const embedding = this.faceNetModel.predict(normalized);
            const reshaped = embedding.reshape([224]);
            
            let embedding512;
            if (reshaped.shape[0] < 512) {
                const padding = tf.zeros([512 - reshaped.shape[0]]);
                embedding512 = tf.concat([reshaped, padding]);
            } else {
                embedding512 = reshaped.slice([0], [512]);
            }
            
            const embArray = Array.from(embedding512.dataSync());
            const norm = Math.sqrt(embArray.reduce((sum, val) => sum + val * val, 0));
            return embArray.map(val => val / norm);
        });
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

    averageEmbeddings(embeddings) {
        const sum = new Array(512).fill(0);
        embeddings.forEach(emb => {
            emb.forEach((val, i) => sum[i] += val);
        });
        const avg = sum.map(val => val / embeddings.length);
        const norm = Math.sqrt(avg.reduce((s, v) => s + v * v, 0));
        return avg.map(v => v / norm);
    }

    cleanup() {
        if (this.faceNetModel) {
            this.faceNetModel.dispose();
        }
        this.isReady = false;
    }
}

window.MLClient = MLClient;