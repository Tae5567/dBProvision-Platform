import asyncio
import json
import os
import logging
from typing import Dict, Any
from app.config import settings

log = logging.getLogger(__name__)


class TerraformExecutor:
    def __init__(self):
        self.terraform_dir = os.path.abspath(settings.terraform_dir)
        self.tf_bin = "terraform"

    async def apply(self, workspace: str, variables: Dict[str, str]) -> Dict[str, Any]:
        work_dir = self.terraform_dir
        env = self._build_env(variables)

        log.info(f"Terraform init — workspace={workspace} dir={work_dir}")
        await self._run(["terraform", "init", "-no-color"], work_dir, env)

        log.info(f"Terraform workspace select/create — {workspace}")
        try:
            await self._run(
                ["terraform", "workspace", "new", workspace, "-no-color"],
                work_dir, env
            )
        except RuntimeError:
            await self._run(
                ["terraform", "workspace", "select", workspace, "-no-color"],
                work_dir, env
            )

        var_args = []
        for k, v in variables.items():
            var_args += ["-var", f"{k}={v}"]

        log.info(f"Terraform apply — workspace={workspace}")
        await self._run(
            ["terraform", "apply", "-auto-approve", "-no-color"] + var_args,
            work_dir, env
        )

        log.info("Terraform output — capturing")
        stdout, _ = await self._run(
            ["terraform", "output", "-json", "-no-color"],
            work_dir, env
        )

        raw = json.loads(stdout)
        outputs = {k: v["value"] for k, v in raw.items()}
        log.info(f"Terraform outputs={outputs}")
        return outputs

    async def destroy(self, workspace: str):
        work_dir = self.terraform_dir
        env = os.environ.copy()

        log.info(f"Terraform destroy — workspace={workspace}")
        await self._run(
            ["terraform", "workspace", "select", workspace, "-no-color"],
            work_dir, env
        )
        await self._run(
            ["terraform", "destroy", "-auto-approve", "-no-color"],
            work_dir, env
        )
        await self._run(
            ["terraform", "workspace", "select", "default", "-no-color"],
            work_dir, env
        )
        await self._run(
            ["terraform", "workspace", "delete", workspace, "-no-color"],
            work_dir, env
        )

    async def _run(self, cmd: list, cwd: str, env: dict = None) -> tuple:
        cmd_str = " ".join(cmd)
        log.info(f"Running: {cmd_str}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            env=env or os.environ.copy(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        stdout_str = stdout.decode()
        stderr_str = stderr.decode()

        if stdout_str:
            log.info(f"stdout: {stdout_str[:500]}")
        if stderr_str:
            log.info(f"stderr: {stderr_str[:500]}")

        if proc.returncode != 0:
            log.error(f"Terraform failed returncode={proc.returncode} stderr={stderr_str}")
            raise RuntimeError(f"Terraform failed: {stderr_str}")

        log.info(f"Command succeeded: {cmd_str}")
        return stdout_str, stderr_str

    def _build_env(self, variables: Dict[str, str]) -> Dict[str, str]:
        env = os.environ.copy()
        for k, v in variables.items():
            env[f"TF_VAR_{k}"] = str(v)
        return env