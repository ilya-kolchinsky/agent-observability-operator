"""Entry point for the runtime coordinator."""

from agent_obs_runtime.bootstrap import STATE


def main() -> None:
    """Run the runtime coordinator bootstrap and expose its import side effects."""
    _ = STATE
    return None


if __name__ == "__main__":
    main()
