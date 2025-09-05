import streamlit as st
import git
from github import Github
import os
import subprocess
from pathlib import Path

st.set_page_config(page_title="GitHub Terminal", layout="wide")

st.title("📂 GitHub Synced Terminal (Multi-User)")

# --- Step 1: Login / Connect ---
if "connected" not in st.session_state:
    st.session_state.connected = False

if not st.session_state.connected:
    github_token = st.text_input("Enter your GitHub Personal Access Token", type="password")
    repo_name = st.text_input("Enter your GitHub repo (user/repo)")

    if st.button("Connect"):
        if github_token and repo_name:
            st.session_state.github_token = github_token
            st.session_state.repo_name = repo_name
            st.session_state.connected = True
            st.experimental_rerun()
        else:
            st.error("Please provide both token and repo.")

# --- Step 2: Initialize user repo ---
if st.session_state.connected:
    LOCAL_PATH = f"user_repo_{st.session_state.repo_name.replace('/', '_')}"
    g = Github(st.session_state.github_token)
    repo = g.get_repo(st.session_state.repo_name)

    # Clone or pull repo
    if not os.path.exists(LOCAL_PATH):
        git.Repo.clone_from(
            f"https://{st.session_state.github_token}@github.com/{st.session_state.repo_name}.git",
            LOCAL_PATH
        )
    else:
        repo_local = git.Repo(LOCAL_PATH)
        repo_local.remotes.origin.pull()

    # Ensure requirements.txt exists
    req_file = os.path.join(LOCAL_PATH, "requirements.txt")
    if not os.path.exists(req_file):
        open(req_file, "w").close()

    # --- Step 3: Terminal state ---
    if "history" not in st.session_state:
        st.session_state.history = []

    command = st.text_input("Enter command:")

    if st.button("Run") and command.strip():
        output = ""
        parts = command.split()
        cmd = parts[0] if parts else ""

        # --- pip install ---
        if cmd == "pip" and len(parts) > 2 and parts[1] == "install":
            package = parts[2]
            with open(req_file, "a") as f:
                f.write(f"{package}\n")
            # push to GitHub
            contents = repo.get_contents("requirements.txt")
            repo.update_file(
                path="requirements.txt",
                message=f"Add {package} to requirements",
                content=open(req_file).read(),
                sha=contents.sha
            )
            output = f"✅ Saved {package} to requirements.txt"

        # --- touch / nano ---
        elif cmd in ["touch", "nano"] and len(parts) > 1:
            filename = parts[1]
            file_path = os.path.join(LOCAL_PATH, filename)
            Path(file_path).touch(exist_ok=True)
            code = st.text_area(f"Edit {filename}", value=open(file_path).read(), height=300)
            if st.button(f"Save {filename}"):
                with open(file_path, "w") as f:
                    f.write(code)
                # push to GitHub
                try:
                    contents = repo.get_contents(filename)
                    repo.update_file(
                        path=filename,
                        message=f"Update {filename}",
                        content=open(file_path).read(),
                        sha=contents.sha
                    )
                except:
                    # file may not exist on GitHub yet
                    repo.create_file(
                        path=filename,
                        message=f"Create {filename}",
                        content=open(file_path).read()
                    )
                st.success(f"✅ {filename} saved to GitHub")
            output = f"Editing {filename}"

        # --- run python file ---
        elif cmd == "python" and len(parts) > 1:
            filename = parts[1]
            file_path = os.path.join(LOCAL_PATH, filename)
            if os.path.exists(file_path):
                try:
                    result = subprocess.run(
                        ["python", file_path],
                        capture_output=True,
                        text=True
                    )
                    output = result.stdout if result.stdout else result.stderr
                except Exception as e:
                    output = str(e)
            else:
                output = f"⚠️ File {filename} does not exist"

        # --- ls ---
        elif cmd == "ls":
            files = os.listdir(LOCAL_PATH)
            output = "\n".join(files)

        # --- cat ---
        elif cmd == "cat" and len(parts) > 1:
            filename = parts[1]
            file_path = os.path.join(LOCAL_PATH, filename)
            if os.path.exists(file_path):
                with open(file_path) as f:
                    output = f.read()
            else:
                output = f"⚠️ File {filename} does not exist"

        # --- rm ---
        elif cmd == "rm" and len(parts) > 1:
            filename = parts[1]
            file_path = os.path.join(LOCAL_PATH, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                # delete from GitHub
                try:
                    contents = repo.get_contents(filename)
                    repo.delete_file(path=filename, message=f"Delete {filename}", sha=contents.sha)
                except:
                    pass
                output = f"✅ {filename} deleted"
            else:
                output = f"⚠️ File {filename} does not exist"

        # --- mkdir ---
        elif cmd == "mkdir" and len(parts) > 1:
            dirname = parts[1]
            dir_path = os.path.join(LOCAL_PATH, dirname)
            os.makedirs(dir_path, exist_ok=True)
            output = f"✅ Directory {dirname} created"

        # --- unsupported ---
        else:
            output = f"⚠️ Command not supported: {command}"

        st.session_state.history.append((command, output))

    # Display terminal history
    st.markdown("### Terminal")
    for cmd, out in st.session_state.history:
        st.markdown(f"$ {cmd}")
        st.code(out, language="bash")
