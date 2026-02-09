"""E2E Selenium tests using Chrome against the Kubernetes-deployed app.

Run:
    pytest tests/e2e/test_selenium.py -v
"""

import uuid

import pytest
from bson import ObjectId
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from tests.e2e.conftest import BASE_URL


# ===================================================================
# Fixtures
# ===================================================================


def _make_chrome_driver():
    """Create a headless Chrome WebDriver with auto-managed ChromeDriver."""
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")

    service = Service(ChromeDriverManager().install())
    d = webdriver.Chrome(service=service, options=opts)
    d.implicitly_wait(5)
    return d


@pytest.fixture(scope="module")
def driver():
    """Create a headless Chrome WebDriver for the test module."""
    d = _make_chrome_driver()
    yield d
    d.quit()


@pytest.fixture()
def fresh_driver():
    """Create a fresh headless Chrome driver (isolated session per test)."""
    d = _make_chrome_driver()
    yield d
    d.quit()


def _unique_username():
    return f"testuser_{uuid.uuid4().hex[:8]}"


def _register_user(driver, username, password):
    """Register a new user through the browser."""
    driver.get(f"{BASE_URL}/register")
    driver.find_element(By.ID, "username").clear()
    driver.find_element(By.ID, "username").send_keys(username)
    driver.find_element(By.ID, "password").clear()
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.ID, "confirm").clear()
    driver.find_element(By.ID, "confirm").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()


def _login_user(driver, username, password):
    """Login through the browser."""
    driver.get(f"{BASE_URL}/login")
    driver.find_element(By.ID, "username").clear()
    driver.find_element(By.ID, "username").send_keys(username)
    driver.find_element(By.ID, "password").clear()
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()


def _logout_user(driver):
    """Logout through the browser by clicking the nav link."""
    logout_links = driver.find_elements(By.LINK_TEXT, "Logout")
    if logout_links:
        logout_links[0].click()
    else:
        driver.get(f"{BASE_URL}/logout")


# ===================================================================
# 1. Registration Tests (Selenium)
# ===================================================================


class TestRegistrationSelenium:
    """Test user registration via the browser."""

    def test_register_page_loads(self, fresh_driver):
        fresh_driver.get(f"{BASE_URL}/register")
        assert "Create Account" in fresh_driver.page_source
        assert fresh_driver.find_element(By.ID, "username")
        assert fresh_driver.find_element(By.ID, "password")
        assert fresh_driver.find_element(By.ID, "confirm")

    def test_register_success_redirects_to_leagues(self, fresh_driver):
        username = _unique_username()
        _register_user(fresh_driver, username, "TestPass123!")
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'My Leagues')]"))
        )
        assert "My Leagues" in fresh_driver.page_source
        assert username in fresh_driver.page_source

    def test_register_duplicate_shows_error(self, fresh_driver):
        username = _unique_username()
        _register_user(fresh_driver, username, "TestPass123!")
        # Logout
        _logout_user(fresh_driver)
        # Try registering again with same username
        _register_user(fresh_driver, username, "TestPass123!")
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "flash"))
        )
        assert "Username already taken" in fresh_driver.page_source

    def test_register_password_mismatch(self, fresh_driver):
        fresh_driver.get(f"{BASE_URL}/register")
        fresh_driver.find_element(By.ID, "username").send_keys(_unique_username())
        fresh_driver.find_element(By.ID, "password").send_keys("pass1")
        fresh_driver.find_element(By.ID, "confirm").send_keys("pass2")
        fresh_driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "flash"))
        )
        assert "Passwords do not match" in fresh_driver.page_source

    def test_register_link_from_login_page(self, fresh_driver):
        fresh_driver.get(f"{BASE_URL}/login")
        register_link = fresh_driver.find_element(By.LINK_TEXT, "Register")
        register_link.click()
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Create Account')]"))
        )
        assert "Create Account" in fresh_driver.page_source


# ===================================================================
# 2. Login Tests (Selenium)
# ===================================================================


class TestLoginSelenium:
    """Test login via the browser."""

    def test_login_page_loads(self, fresh_driver):
        fresh_driver.get(f"{BASE_URL}/login")
        assert "Login" in fresh_driver.title or "Login" in fresh_driver.page_source
        assert fresh_driver.find_element(By.ID, "username")
        assert fresh_driver.find_element(By.ID, "password")

    def test_login_success(self, fresh_driver):
        username = _unique_username()
        password = "TestPass123!"
        # Register first
        _register_user(fresh_driver, username, password)
        # Logout
        _logout_user(fresh_driver)
        # Login
        _login_user(fresh_driver, username, password)
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'My Leagues')]"))
        )
        assert "My Leagues" in fresh_driver.page_source

    def test_login_wrong_password(self, fresh_driver):
        username = _unique_username()
        _register_user(fresh_driver, username, "correct_pass")
        _logout_user(fresh_driver)
        _login_user(fresh_driver, username, "wrong_pass")
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "flash"))
        )
        assert "Invalid username or password" in fresh_driver.page_source

    def test_login_nonexistent_user(self, fresh_driver):
        _login_user(fresh_driver, "nonexistent_user_xyz", "password")
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "flash"))
        )
        assert "Invalid username or password" in fresh_driver.page_source

    def test_login_link_from_register_page(self, fresh_driver):
        fresh_driver.get(f"{BASE_URL}/register")
        login_link = fresh_driver.find_element(By.LINK_TEXT, "Login")
        login_link.click()
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'Login')]"))
        )
        assert fresh_driver.find_element(By.ID, "username")


# ===================================================================
# 3. Logout Tests (Selenium)
# ===================================================================


class TestLogoutSelenium:
    """Test logout via the browser."""

    def test_logout_redirects_to_login(self, fresh_driver):
        username = _unique_username()
        _register_user(fresh_driver, username, "TestPass123!")
        _logout_user(fresh_driver)
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'Login')]"))
        )
        assert "/login" in fresh_driver.current_url or "Login" in fresh_driver.page_source

    def test_logout_prevents_access_to_protected_pages(self, fresh_driver):
        username = _unique_username()
        _register_user(fresh_driver, username, "TestPass123!")
        _logout_user(fresh_driver)
        # Try to access leagues page directly
        fresh_driver.get(f"{BASE_URL}/leagues")
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        # Should be redirected to login
        assert "/login" in fresh_driver.current_url

    def test_nav_shows_logout_when_logged_in(self, fresh_driver):
        username = _unique_username()
        _register_user(fresh_driver, username, "TestPass123!")
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "Logout"))
        )
        assert fresh_driver.find_element(By.LINK_TEXT, "Logout")

    def test_nav_shows_login_when_logged_out(self, fresh_driver):
        fresh_driver.get(f"{BASE_URL}/login")
        nav = fresh_driver.find_element(By.TAG_NAME, "nav")
        assert "Login" in nav.text


# ===================================================================
# 4. Leagues Page Tests (Selenium)
# ===================================================================


class TestLeaguesPageSelenium:
    """Test the leagues listing page via the browser."""

    def test_leagues_page_loads(self, fresh_driver):
        username = _unique_username()
        _register_user(fresh_driver, username, "TestPass123!")
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'My Leagues')]"))
        )
        assert "My Leagues" in fresh_driver.page_source

    def test_leagues_page_shows_zero_for_new_user(self, fresh_driver):
        username = _unique_username()
        _register_user(fresh_driver, username, "TestPass123!")
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '0 leagues')]"))
        )
        assert "0 leagues" in fresh_driver.page_source

    def test_leagues_page_has_add_league_button(self, fresh_driver):
        username = _unique_username()
        _register_user(fresh_driver, username, "TestPass123!")
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "Add League"))
        )
        add_btn = fresh_driver.find_element(By.LINK_TEXT, "Add League")
        assert add_btn.is_displayed()

    def test_add_league_button_navigates(self, fresh_driver):
        username = _unique_username()
        _register_user(fresh_driver, username, "TestPass123!")
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "Add League"))
        )
        fresh_driver.find_element(By.LINK_TEXT, "Add League").click()
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'Add League')]"))
        )
        assert "ESPN League ID" in fresh_driver.page_source


# ===================================================================
# 5. Add League Form Tests (Selenium)
# ===================================================================


class TestAddLeagueSelenium:
    """Test the add league form via the browser."""

    @pytest.fixture(autouse=True)
    def _setup(self, fresh_driver):
        self.driver = fresh_driver
        username = _unique_username()
        _register_user(self.driver, username, "TestPass123!")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "Add League"))
        )

    def test_add_league_form_fields(self):
        self.driver.get(f"{BASE_URL}/leagues/add")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "name"))
        )
        assert self.driver.find_element(By.ID, "name")
        assert self.driver.find_element(By.ID, "espn_league_id")
        assert self.driver.find_element(By.ID, "espn_year")
        assert self.driver.find_element(By.ID, "espn_s2")
        assert self.driver.find_element(By.ID, "espn_swid")

    def test_add_league_year_default(self):
        self.driver.get(f"{BASE_URL}/leagues/add")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "espn_year"))
        )
        year_input = self.driver.find_element(By.ID, "espn_year")
        assert year_input.get_attribute("value") == "2024"

    def test_add_league_invalid_espn_creds_shows_error(self):
        self.driver.get(f"{BASE_URL}/leagues/add")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "name"))
        )
        self.driver.find_element(By.ID, "name").send_keys("TestLeague_Selenium")
        self.driver.find_element(By.ID, "espn_league_id").send_keys("99999999")
        # Clear default year and enter new one
        year_field = self.driver.find_element(By.ID, "espn_year")
        year_field.clear()
        year_field.send_keys("2024")
        self.driver.find_element(By.ID, "espn_s2").send_keys("fake_cookie")
        self.driver.find_element(By.ID, "espn_swid").send_keys("{00000000-0000-0000-0000-000000000000}")
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        WebDriverWait(self.driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "flash"))
        )
        assert "Could not connect to ESPN" in self.driver.page_source

    def test_add_league_back_link(self):
        self.driver.get(f"{BASE_URL}/leagues/add")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "back-link"))
        )
        back_link = self.driver.find_element(By.CLASS_NAME, "back-link")
        assert "Back to leagues" in back_link.text
        back_link.click()
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'My Leagues')]"))
        )


# ===================================================================
# 6. League with Direct DB Data Tests (Selenium)
# ===================================================================


class TestLeagueWithDBDataSelenium:
    """Test league features using directly inserted MongoDB data."""

    @pytest.fixture(autouse=True)
    def _setup(self, fresh_driver, mongo_db, mongo_port_forward):
        self.driver = fresh_driver
        self.db = mongo_db
        self.username = _unique_username()
        self.password = "TestPass123!"
        _register_user(self.driver, self.username, self.password)
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'My Leagues')]"))
        )
        # Find user in MongoDB
        user_doc = self.db["users"].find_one({"username": self.username})
        self.user_id = user_doc["_id"]
        yield
        # Cleanup
        self.db["leagues"].delete_many({"user_id": self.user_id})

    def _insert_league(self, name="TestLeague_Selenium"):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        doc = {
            "user_id": self.user_id,
            "name": name,
            "espn_league_id": 12345,
            "espn_year": 2024,
            "espn_s2": "fake",
            "espn_swid": "{fake}",
            "created_at": now,
            "updated_at": now,
        }
        result = self.db["leagues"].insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def test_league_appears_in_list(self):
        self._insert_league("TestLeague_Visible")
        self.driver.get(f"{BASE_URL}/leagues")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'TestLeague_Visible')]"))
        )
        assert "TestLeague_Visible" in self.driver.page_source
        assert "1 league" in self.driver.page_source

    def test_league_shows_espn_details(self):
        self._insert_league("TestLeague_Details")
        self.driver.get(f"{BASE_URL}/leagues")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'TestLeague_Details')]"))
        )
        assert "12345" in self.driver.page_source
        assert "2024" in self.driver.page_source

    def test_delete_league_button_present(self):
        self._insert_league("TestLeague_DeleteBtn")
        self.driver.get(f"{BASE_URL}/leagues")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".btn-danger"))
        )
        delete_btn = self.driver.find_element(By.CSS_SELECTOR, ".btn-danger")
        assert "Delete" in delete_btn.text

    def test_league_name_links_to_standings(self):
        league = self._insert_league("TestLeague_Link")
        league_id = str(league["_id"])
        self.driver.get(f"{BASE_URL}/leagues")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'TestLeague_Link')]"))
        )
        link = self.driver.find_element(By.XPATH, "//a[.//span[contains(text(), 'TestLeague_Link')]]")
        href = link.get_attribute("href")
        assert f"/leagues/{league_id}/standings" in href

    def test_analytics_page_loads_no_data(self):
        league = self._insert_league("TestLeague_AnalyticsSel")
        league_id = str(league["_id"])
        self.driver.get(f"{BASE_URL}/leagues/{league_id}/analytics")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Player Analytics')]"))
        )
        assert "No analytics data available" in self.driver.page_source

    def test_multiple_leagues_shown(self):
        self._insert_league("TestLeague_Multi1")
        self._insert_league("TestLeague_Multi2")
        self.driver.get(f"{BASE_URL}/leagues")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '2 leagues')]"))
        )
        assert "TestLeague_Multi1" in self.driver.page_source
        assert "TestLeague_Multi2" in self.driver.page_source


# ===================================================================
# 7. Full Workflow Tests (Selenium)
# ===================================================================


class TestFullWorkflowSelenium:
    """Test complete user workflows end-to-end in the browser."""

    def test_register_login_logout_cycle(self, fresh_driver):
        """Full cycle: register → see leagues → logout → login → see leagues."""
        username = _unique_username()
        password = "CyclePass123!"

        # Step 1: Register
        _register_user(fresh_driver, username, password)
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'My Leagues')]"))
        )
        assert username in fresh_driver.page_source

        # Step 2: Logout
        _logout_user(fresh_driver)
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'Login')]"))
        )

        # Step 3: Login
        _login_user(fresh_driver, username, password)
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'My Leagues')]"))
        )
        assert username in fresh_driver.page_source

        # Step 4: Logout again
        _logout_user(fresh_driver)
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'Login')]"))
        )

    def test_register_and_try_add_league(self, fresh_driver):
        """Register → navigate to add league → try adding with bad creds."""
        username = _unique_username()
        _register_user(fresh_driver, username, "TestPass123!")
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "Add League"))
        )

        # Navigate to add league
        fresh_driver.find_element(By.LINK_TEXT, "Add League").click()
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.ID, "name"))
        )

        # Fill in form with invalid ESPN credentials
        fresh_driver.find_element(By.ID, "name").send_keys("My Test League")
        fresh_driver.find_element(By.ID, "espn_league_id").send_keys("99999999")
        year_field = fresh_driver.find_element(By.ID, "espn_year")
        year_field.clear()
        year_field.send_keys("2024")
        fresh_driver.find_element(By.ID, "espn_s2").send_keys("invalid_cookie")
        fresh_driver.find_element(By.ID, "espn_swid").send_keys("{bad-swid}")
        fresh_driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # Should show ESPN error
        WebDriverWait(fresh_driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "flash"))
        )
        assert "Could not connect to ESPN" in fresh_driver.page_source

    def test_protected_route_redirect_after_login(self, fresh_driver):
        """Access a protected page while logged out, then login and get redirected back."""
        username = _unique_username()
        password = "TestPass123!"

        # Register first, then logout
        _register_user(fresh_driver, username, password)
        _logout_user(fresh_driver)

        # Try to access /leagues directly (should redirect to login with next param)
        fresh_driver.get(f"{BASE_URL}/leagues")
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        assert "/login" in fresh_driver.current_url

        # Login
        fresh_driver.find_element(By.ID, "username").send_keys(username)
        fresh_driver.find_element(By.ID, "password").send_keys(password)
        fresh_driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        WebDriverWait(fresh_driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'My Leagues')]"))
        )
        # Should be on leagues page now
        assert "/leagues" in fresh_driver.current_url or "My Leagues" in fresh_driver.page_source
