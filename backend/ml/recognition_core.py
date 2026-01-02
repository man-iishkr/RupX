"""
Face recognition core - wraps existing logic from app.py
Preserves original cosine similarity and recognition functions
"""
import numpy as np
from numpy.linalg import norm
from numpy import dot
import threading
import time

def cosine_similarity(a, b):
    """
    Calculate cosine similarity between two embeddings
    FIXED: Added explicit type casting to prevent NumPy 2.x dict/float errors
    """
    # Ensure inputs are numpy arrays of floats to avoid 'float * dict' errors
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    
    # Flatten just in case embeddings are wrapped in extra dimensions
    a = a.flatten()
    b = b.flatten()
    
    denominator = (norm(a) * norm(b))
    if denominator == 0:
        return 0.0
    return float(dot(a, b) / denominator)

def recognize_face(embedding, embeddings_dict, threshold=0.38):
    """
    Recognize face from embedding using cosine similarity
    ORIGINAL LOGIC PRESERVED
    """
    if not embeddings_dict:
        return ("Unknown", 0.0)

    results = []
    for name, emb in embeddings_dict.items():
        try:
            score = cosine_similarity(embedding, emb)
            results.append((name, score))
        except Exception as e:
            print(f"Recognition error for {name}: {e}")
            continue

    if not results:
        return ("Unknown", 0.0)

    results.sort(key=lambda x: x[1], reverse=True)
    best_match = results[0]
    
    return best_match if best_match[1] > threshold else ("Unknown", best_match[1])

def calculate_iou(box1, box2):
    """
    Fast IOU calculation for face tracking
    FIXED: Added type casting to ensure coordinate math works on all NumPy versions
    """
    # Convert to standard float list/array to avoid dict-like object issues
    b1 = np.asarray(box1, dtype=np.float64).flatten()
    b2 = np.asarray(box2, dtype=np.float64).flatten()
    
    x1_1, y1_1, x2_1, y2_1 = b1
    x1_2, y1_2, x2_2, y2_2 = b2
    
    xi1 = max(x1_1, x1_2)
    yi1 = max(y1_1, y1_2)
    xi2 = min(x2_1, x2_2)
    yi2 = min(y2_1, y2_2)
    
    inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    
    box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
    box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
    union_area = box1_area + box2_area - inter_area
    
    return float(inter_area / union_area) if union_area > 0 else 0.0

class FaceTracker:
    """
    Face tracking system - preserves original logic from app.py
    Tracks faces across frames to avoid repeated recognition
    """
    
    def __init__(self):
        self.tracked_faces = {}
        self.next_face_id = 0
        self.lock = threading.Lock()
    
    def update(self, detected_faces, embeddings_dict):
        """
        Update tracked faces with new detections
        """
        current_time = time.time()
        detected_ids = set()
        results = []
        
        with self.lock:
            for bbox, embedding in detected_faces:
                matched_id = None
                best_iou = 0.2
                
                for face_id, face_data in self.tracked_faces.items():
                    iou = calculate_iou(bbox, face_data['bbox'])
                    if iou > best_iou:
                        best_iou = iou
                        matched_id = face_id
                
                if matched_id is not None:
                    # Update existing face
                    self.tracked_faces[matched_id]['bbox'] = bbox
                    self.tracked_faces[matched_id]['last_seen'] = current_time
                    detected_ids.add(matched_id)
                    
                    # Only recognize if not already recognized
                    if not self.tracked_faces[matched_id].get('recognized', False):
                        name, score = recognize_face(embedding, embeddings_dict)
                        self.tracked_faces[matched_id]['name'] = name
                        self.tracked_faces[matched_id]['score'] = score
                        self.tracked_faces[matched_id]['recognized'] = True
                    
                    results.append((
                        matched_id,
                        bbox,
                        self.tracked_faces[matched_id]['name'],
                        self.tracked_faces[matched_id]['score']
                    ))
                
                else:
                    # New face
                    new_id = self.next_face_id
                    self.next_face_id += 1
                    
                    name, score = recognize_face(embedding, embeddings_dict)
                    
                    self.tracked_faces[new_id] = {
                        'bbox': bbox,
                        'name': name,
                        'score': score,
                        'recognized': True,
                        'last_seen': current_time,
                        'created': current_time
                    }
                    detected_ids.add(new_id)
                    results.append((new_id, bbox, name, score))
            
            # Remove old faces (1.5s timeout)
            to_remove = [fid for fid in self.tracked_faces.keys() 
                        if fid not in detected_ids and 
                        (current_time - self.tracked_faces[fid]['last_seen']) > 1.5]
            
            for face_id in to_remove:
                del self.tracked_faces[face_id]
        
        return results
    
    def clear(self):
        with self.lock:
            self.tracked_faces.clear()
            self.next_face_id = 0

    def get_tracked_count(self):
        with self.lock:
            return len(self.tracked_faces)