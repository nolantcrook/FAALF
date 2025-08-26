import boto3
import json
import os
from dotenv import load_dotenv

def test_lambda_function():
    """Test the Lambda function using boto3"""
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Get region from .env file
    region = os.getenv('region')
    
    # Create Lambda client
    lambda_client = boto3.client('lambda', region_name=region)
    
    # Test payload
    test_payload = {
        "task": "search the internet for hte latest AI news and summarize it",
        "execute": True
    }
    
    try:
        # Invoke the Lambda function
        response = lambda_client.invoke(
            FunctionName='faalf-function',
            InvocationType='RequestResponse',
            Payload=json.dumps(test_payload)
        )
        
        # Parse the response
        status_code = response['StatusCode']
        response_payload = json.loads(response['Payload'].read())
        
        print(f"Status Code: {status_code}")
        print(f"Response: {response_payload}")
        
        # Check for errors
        if 'FunctionError' in response:
            print(f"Function Error: {response['FunctionError']}")
            
        return response_payload
        
    except Exception as e:
        print(f"Error invoking Lambda function: {e}")
        return None

if __name__ == "__main__":
    result = test_lambda_function()
    if result:
        print("Lambda function test successful!")
    else:
        print("Lambda function test failed!")