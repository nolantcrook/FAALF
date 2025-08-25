import json
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name, region_name=None):
    """Retrieve secret from AWS Secrets Manager"""
    if region_name is None:
        region_name = os.environ.get('AWS_REGION')
    
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        return get_secret_value_response['SecretString']
    except ClientError as e:
        print(f"Error retrieving secret {secret_name}: {e}")
        return None

def create_fallback_response(task, temp_dir):
    """Create a fallback response when Claude Code isn't available or authenticated"""
    fallback_output = f"# Fallback: Claude Code not available or not authenticated\n"
    fallback_output += f"# Task: {task}\n\n"
    
    # Simple pattern matching for common requests
    if 'hello world' in task.lower():
        script_content = 'print("Hello, World!")'
        file_path = Path(temp_dir) / 'hello_world.py'
        file_path.write_text(script_content)
        fallback_output += 'Created hello_world.py with basic Hello World script.\n'
    elif any(word in task.lower() for word in ['calculator', 'math']):
        script_content = '''def calculator(a, b, operation):
    operations = {
        '+': lambda x, y: x + y,
        '-': lambda x, y: x - y,
        '*': lambda x, y: x * y,
        '/': lambda x, y: x / y if y != 0 else 'Cannot divide by zero'
    }
    return operations.get(operation, lambda x, y: 'Invalid operation')(a, b)

# Example usage
result = calculator(10, 5, '+')
print(f"10 + 5 = {result}")'''
        file_path = Path(temp_dir) / 'calculator.py'
        file_path.write_text(script_content)
        fallback_output += 'Created calculator.py with basic calculator functionality.\n'
    else:
        # Generic script
        script_content = f'''# Generated script for: {task}
# This is a fallback implementation

def main():
    print('Task: {task}')
    print('This is a fallback implementation.')
    print('For full functionality, please ensure Claude Code is properly authenticated.')

if __name__ == "__main__":
    main()'''
        file_path = Path(temp_dir) / 'generated_script.py'
        file_path.write_text(script_content)
        fallback_output += 'Created generic Python script.\n'
    
    return {
        'stdout': fallback_output,
        'stderr': '',
        'exitCode': 0
    }

def execute_claude(task, temp_dir, env, current_user=None):
    """Execute Claude CLI using a simplified approach"""
    try:
        print(f'Executing Claude CLI with task: {task}')
        
        # Set up Claude config directory in /tmp
        claude_home = '/tmp/claude-home'
        
        # Run Claude CLI directly as the current user (no su needed)
        cmd = f'cd "{temp_dir}" && HOME="{claude_home}" ANTHROPIC_API_KEY="{env["ANTHROPIC_API_KEY"]}" echo "{task.replace('"', '\\"')}" | claude --dangerously-skip-permissions --print'
        
        process = subprocess.run(
            ['bash', '-c', cmd],
            env={
                **env,
                'HOME': claude_home,
                'CI': 'true',
                'TERM': 'dumb',
                'NO_COLOR': '1',
                'ANTHROPIC_API_KEY': env['ANTHROPIC_API_KEY']
            },
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        print(f'Claude CLI completed with exit code: {process.returncode}')
        print(f'Claude output length: {len(process.stdout)}')
        if process.stderr:
            print(f'Claude stderr: {process.stderr[:200]}')
        
        return {
            'stdout': process.stdout,
            'stderr': process.stderr,
            'exitCode': process.returncode
        }
        
    except subprocess.TimeoutExpired:
        raise Exception('Claude CLI execution timeout')
    except Exception as error:
        print(f'Claude CLI process error: {str(error)}')
        raise error


def execute_python_files(temp_dir):
    """Execute Python files in the directory"""
    results = []
    
    try:
        temp_path = Path(temp_dir)
        
        for file_path in temp_path.glob('*.py'):
            try:
                result = subprocess.run(
                    ['python', str(file_path)],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=60  # 1 minute timeout per file
                )
                
                results.append({
                    'file': file_path.name,
                    'stdout': result.stdout,
                    'stderr': result.stderr if result.stderr else None,
                    'return_code': result.returncode
                })
            except subprocess.TimeoutExpired:
                results.append({
                    'file': file_path.name,
                    'error': 'Execution timeout'
                })
            except Exception as error:
                results.append({
                    'file': file_path.name,
                    'error': str(error)
                })
    except Exception as error:
        print(f'Error reading directory: {error}')
    
    return results


def handler(event, context):
    """AWS Lambda handler function"""
    try:
        # Extract task from event
        task = event.get('task', '')
        execute = event.get('execute', False)
        
        if not task:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'No task provided'
                })
            }
        
        # Create a temporary directory for the work
        temp_dir = tempfile.mkdtemp(prefix='claude-')
        
        # Make temp directory accessible to claude-user
        os.chmod(temp_dir, 0o777)
        
        claude_output = ''
        claude_error = None
        exit_code = 0

        # Get API key from secrets manager
        api_key = get_secret('anthropic-api-key-secret')
        os.environ['ANTHROPIC_API_KEY'] = api_key
        if not api_key:
            raise Exception('Failed to retrieve ANTHROPIC_API_KEY from secrets manager')
        
        try:
            # Use the current Lambda user instead of creating a new one
            current_user = subprocess.run(['whoami'], capture_output=True, text=True).stdout.strip()
            print(f"Running as user: {current_user}")


            # Set up environment variables for Claude authentication
            env = {
                **os.environ,
                'HOME': os.environ.get('HOME', '/tmp'),
                'ANTHROPIC_API_KEY': api_key
            }
            
            # Create a clean Claude configuration directory for claude-user
            claude_home = Path('/tmp/claude-home')
            claude_home_dir = claude_home / '.claude'
            claude_home_dir.mkdir(parents=True, exist_ok=True)
            
            claude_config_path = claude_home_dir / 'settings.json'
            claude_auth_path = claude_home / '.claude.json'
            
            # Create auth file
            claude_auth = {
                'apiKey': env['ANTHROPIC_API_KEY']
            }
            claude_auth_path.write_text(json.dumps(claude_auth))
            
            # Create minimal settings file
            claude_settings = {
                'apiKey': env['ANTHROPIC_API_KEY']
            }
            claude_config_path.write_text(json.dumps(claude_settings))
            
            # Config files should be accessible to current user
            os.chmod(claude_home, 0o755)
            os.chmod(claude_home_dir, 0o755)
            
            # Execute Claude using the working claude-docker approach
            result = execute_claude(task, temp_dir, env, current_user)
            
            claude_output = result['stdout']
            claude_error = result['stderr'] or None
            exit_code = result['exitCode']
            
        except Exception as error:
            print(f'Claude CLI failed: {str(error)}')
            
            # If Claude CLI fails, use fallback
            fallback_result = create_fallback_response(task, temp_dir)
            claude_output = fallback_result['stdout']
            claude_error = f'Claude CLI Error: {str(error)}'
            exit_code = fallback_result['exitCode']
        
        # Build response
        response = {
            'claude_output': claude_output,
            'claude_error': claude_error,
            'return_code': exit_code
        }
        
        # If execute is requested and we have files, try to run them
        if execute and exit_code == 0:
            try:
                execution_results = execute_python_files(temp_dir)
                response['execution_results'] = execution_results
            except Exception as error:
                print(f'Error executing files: {error}')
                response['execution_error'] = str(error)
        
        # Read and include any created files in response
        try:
            temp_path = Path(temp_dir)
            created_files = {}
            for file_path in temp_path.glob('*'):
                if file_path.suffix in ['.py', '.js', '.txt'] and file_path.is_file():
                    try:
                        created_files[file_path.name] = file_path.read_text()
                    except Exception as error:
                        print(f'Failed to read file {file_path.name}: {error}')
            response['created_files'] = created_files
        except Exception as error:
            print(f'Failed to read created files: {error}')

        # Clean up temp directory
        try:
            shutil.rmtree(temp_dir)
        except Exception as error:
            print(f'Failed to clean up temp directory: {error}')
        
        return {
            'statusCode': 200,
            'body': json.dumps(response)
        }
        
    except Exception as error:
        print(f'Lambda function error: {error}')
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Lambda function error: {str(error)}'
            })
        }