import csv
import random
import time
import threading
from locust import HttpUser, task, between
from locust import events

def load_users_from_csv(filepath):
    users = []
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            users.append(row)
    return users

user_pool = load_users_from_csv("test_users_with_tokens.csv")

class UserAssigner:
    def __init__(self):
        self._index = 0
        self._lock = threading.Lock()
    
    def get_next_user(self):
        with self._lock:
            user = user_pool[self._index % len(user_pool)]
            self._index += 1
            return user
    
    def reset(self):
        with self._lock:
            self._index = 0

user_assigner = UserAssigner()

@events.test_stop.add_listener
def reset_user_counter(environment, **kwargs):
    user_assigner.reset()

SAMPLE_HASHTAGS = ["#mastodon", "#mystodon", "#antisocial", "#technoo"]
SAMPLE_CONTENT = ["Am alive", "Non stop pop", "Testing the long way", "Deep thoughts", "Traffic crazy"]

class MastodonUser(HttpUser):
    wait_time = between(1, 5)
    
    def on_start(self):
        
        self.user = user_assigner.get_next_user()
        self.headers = {
            "Authorization": f"Bearer {self.user['access_token']}",
            "Content-Type": "application/json"
        }
        
        self.last_post_id = None
        self.followed_users = []
        self.bookmarked_posts = []
        self.available_users = []

        for u in user_pool:
            user_id = u.get('account_id')
            current_user_id = self.user.get('account_id')
            if user_id != current_user_id:
                self.available_users.append(user_id)
    
    def on_stop(self):
    
        for user_id in self.followed_users:
                response = self.client.post(f"/api/v1/accounts/{user_id}/unfollow", headers=self.headers)
                
        for post_id in self.bookmarked_posts:
            response = self.client.post(f"/api/v1/statuses/{post_id}/unbookmark", headers=self.headers)

        self.last_post_id = None
        self.followed_users.clear()
        self.bookmarked_posts.clear()
        self.available_users.clear()
    
    # Core timeline and feed tasks
    @task(2)
    def fetch_home_timeline(self):
        params = {"limit": 30}
        self.client.get("/api/v1/timelines/home", headers=self.headers, params=params)

    @task(2)
    def fetch_public_timeline(self):
        timeline_type = random.choice(["public", "public?local=true"])
        params = {"limit": 30}
        self.client.get(f"/api/v1/timelines/{timeline_type}", headers=self.headers, params=params)

    @task(1)
    def fetch_hashtag_timeline(self):
        hashtag = random.choice(SAMPLE_HASHTAGS).replace("#", "")
        params = {"limit": 30}
        self.client.get(f"/api/v1/timelines/tag/{hashtag}", headers=self.headers, params=params)

    # Posting and content creation
    @task(2)
    def post_status(self):
        content_base = random.choice(SAMPLE_CONTENT)
        hashtag = random.choice(SAMPLE_HASHTAGS)
        status_text = f"{content_base} {hashtag} #{random.randint(1, 1000)}"
        
        payload = {
            "status": status_text,
            "visibility": random.choice(["public", "unlisted", "private"]),
            "sensitive": random.choice([False, False, False, True])
        }
        
        response = self.client.post("/api/v1/statuses", headers=self.headers, json=payload)
        if response.status_code == 200:
            self.last_post_id = response.json().get("id")

    @task(1)
    def post_with_media(self):
        status_text = f"Check out this! {random.choice(SAMPLE_HASHTAGS)}"
        payload = {
            "status": status_text,
            "media_ids": [],
            "visibility": "public"
        }
        self.client.post("/api/v1/statuses", headers=self.headers, json=payload)

    @task(1)
    def reply_to_status(self):
        if self.last_post_id:
            reply_text = random.choice([
                "No",
                "Yes",
                "Hmmm",
                "Absolutely",
                "Absolutely not!"
            ])
            payload = {
                "status": reply_text,
                "in_reply_to_id": self.last_post_id,
                "visibility": "public"
            }
            self.client.post("/api/v1/statuses", headers=self.headers, json=payload)

    # Social interactions
    @task(2)
    def favourite_last_status(self):
        if self.last_post_id:
            self.client.post(f"/api/v1/statuses/{self.last_post_id}/favourite", headers=self.headers)

    @task(1)
    def unfavourite_status(self):
        if self.last_post_id:
            self.client.post(f"/api/v1/statuses/{self.last_post_id}/unfavourite", headers=self.headers)

    @task(1)
    def boost_last_status(self):
        if self.last_post_id:
            self.client.post(f"/api/v1/statuses/{self.last_post_id}/reblog", headers=self.headers)

    @task(1)
    def unboost_status(self):
        if self.last_post_id:
            self.client.post(f"/api/v1/statuses/{self.last_post_id}/unreblog", headers=self.headers)

    @task(1)
    def bookmark_status(self):
        if self.last_post_id:
            response = self.client.post(f"/api/v1/statuses/{self.last_post_id}/bookmark", headers=self.headers)
            if response.status_code == 200:
                self.bookmarked_posts.append(self.last_post_id)

    @task(1)
    def unbookmark_status(self):
        if self.last_post_id:
            response = self.client.post(f"/api/v1/statuses/{self.last_post_id}/unbookmark", headers=self.headers)
            if response.status_code == 200:
                if self.last_post_id in self.bookmarked_posts:
                    self.bookmarked_posts.remove(self.last_post_id)

    @task(1)
    def get_bookmarks(self):
        self.client.get("/api/v1/bookmarks", headers=self.headers)

    # User management and social features
    @task(2)
    def follow_another_user(self):
        if not self.available_users:
            return
        
        if len(self.followed_users) >= len(self.available_users):
            return
        
        max_attempts = len(self.available_users)
        attempts = 0
        
        while attempts < max_attempts:
            account_id = random.choice(self.available_users)
            
            if account_id not in self.followed_users:
                response = self.client.post(f"/api/v1/accounts/{account_id}/follow", headers=self.headers)
                if response.status_code == 200:
                    self.followed_users.append(account_id)
                    return
                else:
                    return
            
            attempts += 1
            
    @task(2)
    def unfollow_user(self):

        if self.followed_users:
            account_id = random.choice(self.followed_users) 
            response = self.client.post(f"/api/v1/accounts/{account_id}/unfollow", headers=self.headers)
            
            if response.status_code == 200:
                self.followed_users.remove(account_id)
        
    @task(1)
    def get_followers(self):
        account_id = self.user.get("account_id", "1")
        self.client.get(f"/api/v1/accounts/{account_id}/followers", headers=self.headers)

    @task(1)
    def get_following(self):
        account_id = self.user.get("account_id", "1")
        self.client.get(f"/api/v1/accounts/{account_id}/following", headers=self.headers)

    @task(1)
    def search_users(self):
        search_terms = ["test", "user", "admin", "bot", "demo"]
        query = random.choice(search_terms)
        params = {"q": query, "type": "accounts", "limit": 10}
        self.client.get("/api/v2/search", headers=self.headers, params=params)

    @task(1)
    def search_content(self):
        search_terms = SAMPLE_HASHTAGS + ["mastodon", "test", "hello"]
        query = random.choice(search_terms)
        params = {"q": query, "type": "statuses", "limit": 10}
        self.client.get("/api/v2/search", headers=self.headers, params=params)

    # Account and notification management
    @task(2)
    def get_notifications(self):
        params = {"limit": 30}
        self.client.get("/api/v1/notifications", headers=self.headers, params=params)

    @task(1)
    def get_account_info(self):
        self.client.get("/api/v1/accounts/verify_credentials", headers=self.headers)

    @task(1)
    def update_profile(self):
        bio_updates = [
            "I like turtles",
            "Nyooom",
            "Hooper",
            "GOAT"
        ]
        payload = {
            "note": random.choice(bio_updates),
            "display_name": f"TestUser{random.randint(1, 500)}"
        }
        self.client.patch("/api/v1/accounts/update_credentials", headers=self.headers, json=payload)

    @task(1)
    def get_instance_info(self):
        self.client.get("/api/v1/instance")

    @task(1)
    def get_trends(self):
        self.client.get("/api/v1/trends", headers=self.headers)

    # List management
    @task(1)
    def get_lists(self):
        self.client.get("/api/v1/lists", headers=self.headers)

    @task(1)
    def create_list(self):
        list_names = ["Basketball", "Friends", "Hockey", "INTeresting People"]
        payload = {"title": f"{random.choice(list_names)} {random.randint(1, 100)}"}
        self.client.post("/api/v1/lists", headers=self.headers, json=payload)

    # Direct messages
    @task(1)
    def get_conversations(self):
        self.client.get("/api/v1/conversations", headers=self.headers)

    # Filters and muting
    @task(1)
    def get_filters(self):
        self.client.get("/api/v1/filters", headers=self.headers)

    @task(1)
    def get_muted_accounts(self):
        self.client.get("/api/v1/mutes", headers=self.headers)

    @task(1)
    def get_blocked_accounts(self):
        self.client.get("/api/v1/blocks", headers=self.headers)

    # Status context and thread exploration
    @task(1)
    def get_status_context(self):
        if self.last_post_id:
            self.client.get(f"/api/v1/statuses/{self.last_post_id}/context", headers=self.headers)

    @task(1)
    def get_status_details(self):
        if self.last_post_id:
            self.client.get(f"/api/v1/statuses/{self.last_post_id}", headers=self.headers)

    # Periodic cleanup task
    @task(1)
    def cleanup_old_data(self):
        if len(self.followed_users) > 20:
            self.followed_users = self.followed_users[-10:]
        if len(self.bookmarked_posts) > 15:
            self.bookmarked_posts = self.bookmarked_posts[-8:]