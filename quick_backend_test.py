import requests
import sys
import json
import time
from datetime import datetime

class QuickAPITester:
    def __init__(self, base_url="https://stackpilot-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=10):
        """Run a single API test with shorter timeout"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)

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
                print(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

def main():
    print("🚀 Quick StackPilot API Tests")
    print("=" * 40)
    
    tester = QuickAPITester()
    
    # Test basic endpoints only
    print("\n1. Testing Root API Endpoint")
    tester.run_test("Root API", "GET", "", 200)
    
    print("\n2. Testing Get Projects")
    tester.run_test("Get Projects", "GET", "projects", 200)
    
    print("\n3. Testing Create Project (Basic)")
    project_data = {
        "name": f"quick-test-{int(time.time())}",
        "sourceType": "text_only",
        "textDescription": "Simple test project",
        "aiProvider": "gpt_5_2",
        "useEmergentKey": True
    }
    success, response = tester.run_test("Create Project", "POST", "projects", 200, data=project_data)
    
    project_id = None
    if success and 'id' in response:
        project_id = response['id']
        print(f"   Created project ID: {project_id}")
        
        print("\n4. Testing Get Project by ID")
        tester.run_test("Get Project by ID", "GET", f"projects/{project_id}", 200)
        
        print("\n5. Testing Delete Project")
        tester.run_test("Delete Project", "DELETE", f"projects/{project_id}", 200)
    
    # Print results
    print("\n" + "=" * 40)
    print(f"📊 Quick Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 Basic API functionality working!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} basic tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())