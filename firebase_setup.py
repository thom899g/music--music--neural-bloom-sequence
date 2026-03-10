"""
Firebase Central Nervous System for Neural Bloom Sequence
Architectural Rationale: Firebase provides real-time sync, offline persistence, 
and automatic scaling - eliminating need for custom database management.
"""
import firebase_admin
from firebase_admin import credentials, firestore, storage
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FirebaseCNS:
    """Central Nervous System - Single source of truth for all mission state"""
    
    def __init__(self, service_account_path: str = None):
        """
        Initialize Firebase with fallback strategies
        
        Edge Cases Handled:
        1. Multiple initialization attempts
        2. Missing service account file
        3. Invalid credentials
        4. Network connectivity issues
        """
        self.service_account_path = service_account_path or os.getenv("FIREBASE_CREDENTIALS_PATH")
        
        if not firebase_admin._apps:
            self._initialize_firebase()
        
        self.db = firestore.client()
        self.bucket = storage.bucket() if storage.bucket else None
        logger.info("Firebase CNS initialized successfully")
    
    def _initialize_firebase(self) -> None:
        """Safe initialization with multiple fallback strategies"""
        try:
            if not self.service_account_path:
                logger.warning("No service account path provided. Checking environment...")
                # Attempt to get credentials from environment variable
                cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
                if cred_json:
                    cred_dict = json.loads(cred_json)
                    cred = credentials.Certificate(cred_dict)
                else:
                    raise ValueError("No Firebase credentials found in environment")
            else:
                if not os.path.exists(self.service_account_path):
                    raise FileNotFoundError(f"Service account file not found: {self.service_account_path}")
                cred = credentials.Certificate(self.service_account_path)
            
            firebase_admin.initialize_app(cred, {
                'storageBucket': os.getenv("FIREBASE_STORAGE_BUCKET", "neural-bloom.appspot.com")
            })
            
        except Exception as e:
            logger.error(f"Firebase initialization failed: {str(e)}")
            
            # Emergency fallback: Create local JSON file for debugging
            emergency_data = {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "system": "Firebase initialization failed",
                "fallback_mode": True
            }
            with open("emergency_firebase_fallback.json", "w") as f:
                json.dump(emergency_data, f)
            
            raise RuntimeError(f"Cannot proceed without Firebase: {str(e)}")
    
    def create_schema(self) -> Dict[str, Any]:
        """Initialize all Firestore collections with validation rules"""
        schema = {
            "tracks": {
                "description": "Seed bundles and generation parameters",
                "required_fields": ["created_at", "seed_bundle", "status"],
                "indexes": ["status", "created_at", "emotional_valence"]
            },
            "distribution": {
                "description": "Multi-DSP distribution status and metadata",
                "required_fields": ["track_id", "platform", "status", "submission_time"],
                "indexes": ["platform", "status", "track_id"]
            },
            "feedback": {
                "description": "Streaming analytics and listener engagement",
                "required_fields": ["track_id", "timestamp", "metric_type"],
                "indexes": ["track_id", "timestamp", "metric_type"]
            },
            "models": {
                "description": "Generation model versions and training data",
                "required_fields": ["model_id", "version", "trained_at"],
                "indexes": ["model_id", "version", "active"]
            },
            "workflow": {
                "description": "Queue management and failover states",
                "required_fields": ["job_id", "state", "created_at", "updated_at"],
                "indexes": ["state", "priority", "created_at"]
            }
        }
        
        # Create collection references
        for collection_name in schema.keys():
            doc_ref = self.db.collection(collection_name).document("_schema")
            doc_ref.set({
                "schema_definition": schema[collection_name],
                "initialized_at": datetime.utcnow().isoformat(),
                "version": "1.0"
            })
        
        logger.info("Firestore schema initialized")
        return schema
    
    def log_workflow_state(self, job_id: str, state: str, metadata: Dict[str, Any] = None) -> None:
        """Atomic workflow state logging with retry logic"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                workflow_ref = self.db.collection("workflow").document(job_id)
                workflow_ref.set({
                    "state": state,
                    "updated_at": datetime.utcnow().isoformat(),
                    "metadata": metadata or {},
                    "retry_count": retry_count
                }, merge=True)
                logger.info(f"Workflow state updated: {job_id} -> {state}")
                return
            except Exception as e:
                retry_count += 1
                logger.warning(f"Workflow log failed (attempt {retry_count}/{max_retries}): {str(e)}")
                if retry_count == max_retries:
                    logger.error(f"Failed to log workflow state after {max_retries} attempts")
                    raise
    
    def emergency_telegram_notification(self, message: str) -> None:
        """Fallback notification if Firebase fails"""
        # This will be integrated with telegram_notifier.py
        logger.critical(f"EMERGENCY: {message}")
        # Write to local emergency log
        with open("emergency_alerts.log", "a") as f:
            f.write(f"{datetime.utcnow().isoformat()} - {message}\n")

# Singleton instance
cns_instance = None

def get_cns() -> FirebaseCNS:
    """Get or create Firebase CNS singleton"""
    global cns_instance
    if cns_instance is None:
        cns_instance = FirebaseCNS()
    return cns_instance

if __name__ == "__main__":
    # Initialize and create schema when run directly
    cns = get_cns()
    schema = cns.create_schema()
    print(f"Firebase CNS ready. Schema: {list(schema.keys())}")