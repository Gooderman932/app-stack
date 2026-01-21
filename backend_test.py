import requests
import sys
import json
import time
from datetime import datetime

class StackPilotAPITester:
    def __init__(self, base_url="https://stackpilot-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.project_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'} if not files else {}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, timeout=30)
                else:
                    response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root API", "GET", "", 200)

    def test_get_projects_empty(self):
        """Test getting projects when empty"""
        return self.run_test("Get Projects (Empty)", "GET", "projects", 200)

    def test_create_project_github(self):
        """Test creating a project with GitHub URL"""
        project_data = {
            "name": f"test-react-project-{int(time.time())}",
            "sourceType": "github_url",
            "sourceUrl": "https://github.com/facebook/react",
            "textDescription": "Testing React repository analysis",
            "aiProvider": "gpt_5_2",
            "useEmergentKey": True,
            "techStackHints": ["Frontend"]
        }
        
        success, response = self.run_test("Create Project (GitHub)", "POST", "projects", 200, data=project_data)
        if success and 'id' in response:
            self.project_id = response['id']
            print(f"   Created project ID: {self.project_id}")
        return success, response

    def test_get_project_by_id(self):
        """Test getting a specific project"""
        if not self.project_id:
            print("❌ Skipped - No project ID available")
            return False, {}
        
        return self.run_test("Get Project by ID", "GET", f"projects/{self.project_id}", 200)

    def test_analyze_project(self):
        """Test analyzing a project"""
        if not self.project_id:
            print("❌ Skipped - No project ID available")
            return False, {}
        
        print("   Note: This may take 30-60 seconds for AI analysis...")
        success, response = self.run_test("Analyze Project", "POST", f"projects/{self.project_id}/analyze", 200)
        
        if success:
            print(f"   Analysis Status: {response.get('status', 'unknown')}")
            tech_stack = response.get('detectedTechStack', {})
            print(f"   Detected Frontend: {tech_stack.get('frontend', 'N/A')}")
            print(f"   Detected Backend: {tech_stack.get('backend', 'N/A')}")
            
        return success, response

    def test_generate_plans(self):
        """Test generating deployment plans"""
        if not self.project_id:
            print("❌ Skipped - No project ID available")
            return False, {}
        
        generate_data = {
            "projectId": self.project_id,
            "generateType": "plans"
        }
        
        print("   Note: This may take 30-60 seconds for AI generation...")
        success, response = self.run_test("Generate Plans", "POST", f"projects/{self.project_id}/generate", 200, data=generate_data)
        
        if success:
            plans = response.get('deploymentPlans', {})
            print(f"   Generated Plans: {list(plans.keys())}")
            
        return success, response

    def test_generate_docs(self):
        """Test generating documentation"""
        if not self.project_id:
            print("❌ Skipped - No project ID available")
            return False, {}
        
        generate_data = {
            "projectId": self.project_id,
            "generateType": "docs"
        }
        
        print("   Note: This may take 30-60 seconds for AI generation...")
        success, response = self.run_test("Generate Docs", "POST", f"projects/{self.project_id}/generate", 200, data=generate_data)
        
        if success:
            docs = response.get('docs', {})
            print(f"   Generated Docs: {list(docs.keys())}")
            
        return success, response

    def test_generate_both(self):
        """Test generating both plans and docs"""
        # Create a new project for this test
        project_data = {
            "name": f"test-both-project-{int(time.time())}",
            "sourceType": "text_only",
            "textDescription": "A React frontend with FastAPI backend and PostgreSQL database",
            "aiProvider": "gpt_5_2",
            "useEmergentKey": True
        }
        
        success, response = self.run_test("Create Project for Both Test", "POST", "projects", 200, data=project_data)
        if not success:
            return False, {}
        
        both_project_id = response['id']
        
        # Analyze first
        success, _ = self.run_test("Analyze Both Project", "POST", f"projects/{both_project_id}/analyze", 200)
        if not success:
            return False, {}
        
        # Generate both
        generate_data = {
            "projectId": both_project_id,
            "generateType": "both"
        }
        
        print("   Note: This may take 60-90 seconds for AI generation...")
        success, response = self.run_test("Generate Both", "POST", f"projects/{both_project_id}/generate", 200, data=generate_data)
        
        if success:
            plans = response.get('deploymentPlans', {})
            docs = response.get('docs', {})
            print(f"   Generated Plans: {list(plans.keys())}")
            print(f"   Generated Docs: {list(docs.keys())}")
            
        return success, response

    def test_get_all_projects(self):
        """Test getting all projects after creation"""
        success, response = self.run_test("Get All Projects", "GET", "projects", 200)
        
        if success and isinstance(response, list):
            print(f"   Total projects: {len(response)}")
            for project in response[:3]:  # Show first 3
                print(f"   - {project.get('name', 'Unknown')} ({project.get('status', 'unknown')})")
                
        return success, response

    def test_delete_project(self):
        """Test deleting a project"""
        if not self.project_id:
            print("❌ Skipped - No project ID available")
            return False, {}
        
        return self.run_test("Delete Project", "DELETE", f"projects/{self.project_id}", 200)

    def test_upload_project(self):
        """Test creating and uploading a ZIP file project"""
        # Create a simple test ZIP file
        import zipfile
        import io
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr('package.json', '{"name": "test-app", "dependencies": {"react": "^18.0.0"}}')
            zip_file.writestr('requirements.txt', 'fastapi==0.104.1\nuvicorn==0.24.0')
        
        zip_buffer.seek(0)
        
        # Create upload project
        project_data = {
            "name": f"test-upload-project-{int(time.time())}",
            "sourceType": "upload",
            "aiProvider": "gpt_5_2",
            "useEmergentKey": True
        }
        
        success, response = self.run_test("Create Upload Project", "POST", "projects", 200, data=project_data)
        if not success:
            return False, {}
        
        upload_project_id = response['id']
        
        # Upload file
        files = {'file': ('test.zip', zip_buffer.getvalue(), 'application/zip')}
        success, response = self.run_test("Upload ZIP File", "POST", f"projects/{upload_project_id}/upload", 200, files=files)
        
        return success, response

def main():
    print("🚀 Starting StackPilot API Tests")
    print("=" * 50)
    
    tester = StackPilotAPITester()
    
    # Test sequence
    tests = [
        tester.test_root_endpoint,
        tester.test_get_projects_empty,
        tester.test_create_project_github,
        tester.test_get_project_by_id,
        tester.test_analyze_project,
        tester.test_generate_plans,
        tester.test_generate_docs,
        tester.test_generate_both,
        tester.test_upload_project,
        tester.test_get_all_projects,
        tester.test_delete_project
    ]
    
    for test in tests:
        try:
            test()
            time.sleep(1)  # Brief pause between tests
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    # Print results
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())