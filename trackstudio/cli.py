"""
TrackStudio CLI - Command-line interface for TrackStudio
"""

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group()
@click.version_option()
def cli():
    """TrackStudio - Multi-Camera Vision Tracking System"""
    pass


@cli.command()
@click.option("--streams", "-s", multiple=True, help="RTSP stream URLs (can specify multiple times)")
@click.option("--config", "-c", type=click.Path(exists=True), help="Configuration file path")
@click.option(
    "--tracker",
    "-t",
    default="rfdetr",
    type=str,  # Allow any string, validation happens later
    help="Vision tracker to use (rfdetr, dummy, or custom)",
)
@click.option("--merger", "-m", default="bev_cluster", help="Cross-camera merger to use")
@click.option("--port", "-p", default=8000, type=int, help="Server port")
@click.option("--host", "-h", default="127.0.0.1", help="Server host")
@click.option("--share", is_flag=True, help="Create public URL")
@click.option("--no-browser", is_flag=True, help="Do not open browser automatically")
@click.option("--vision-fps", default=10.0, type=float, help="Vision processing FPS")
@click.option("--calibration-file", type=click.Path(exists=True), help="Calibration data file")
@click.option("--debug", is_flag=True, help="Enable debug logging")
def run(streams, config, tracker, merger, port, host, share, no_browser, vision_fps, calibration_file, debug):
    """Run TrackStudio server"""

    # Show banner
    console.print(
        Panel.fit("[bold blue]TrackStudio[/bold blue] 🎥\nMulti-Camera Vision Tracking System", border_style="blue")
    )

    # Set up logging
    if debug:
        import logging  # noqa: PLC0415

        logging.basicConfig(level=logging.DEBUG)

    # Load config file if provided
    config_data = {}
    if config:
        with Path(config).open() as f:
            config_data = json.load(f)
            console.print(f"[green]✓[/green] Loaded config from {config}")

    # Use streams from command line or config
    if config_data.get("rtsp_streams") is None:
        config_data["rtsp_streams"] = (
            [*streams] if streams else ["rtsp://localhost:8554/camera0", "rtsp://localhost:8554/camera1"]
        )

    # Import here to avoid circular imports
    from . import launch  # noqa: PLC0415

    # Display configuration
    table = Table(title="Configuration", show_header=False)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Tracker", config_data.get("tracker", tracker))
    table.add_row("Merger", config_data.get("merger", merger))
    table.add_row("Vision FPS", str(config_data.get("vision_fps", vision_fps)))
    table.add_row("Server", f"{config_data.get('server_name', host)}:{config_data.get('server_port', port)}")
    table.add_row("Share", "Yes" if config_data.get("share", share) else "No")
    table.add_row("Streams", str(len(config_data.get("rtsp_streams", []))))

    console.print(table)
    console.print()

    # List streams
    console.print("[bold]Stream URLs:[/bold]")
    for i, stream in enumerate(config_data.get("rtsp_streams", [])):
        console.print(f"  {i + 1}. {stream}")
    console.print()

    try:
        # Launch TrackStudio
        app = launch(
            tracker=config_data.get("tracker", tracker),
            merger=config_data.get("merger", merger),
            vision_fps=config_data.get("vision_fps", vision_fps),
            server_name=config_data.get("server_name", host),
            server_port=config_data.get("server_port", port),
            share=config_data.get("share", share),
            open_browser=config_data.get("open_browser", not no_browser),
            calibration_file=config_data.get("calibration_file", calibration_file),
            rtsp_streams=config_data.get("rtsp_streams", streams),
        )

        # Keep running until interrupted
        app.wait()

    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        if debug:
            import traceback  # noqa: PLC0415

            traceback.print_exc()
        sys.exit(1)


@cli.command()
def demo():
    """Run TrackStudio with demo configuration"""
    from . import demo as run_demo  # noqa: PLC0415

    console.print(
        Panel.fit(
            "[bold blue]TrackStudio Demo Mode[/bold blue]\n🎥 Starting with demo configuration...",
            border_style="blue",
        )
    )

    run_demo()


@cli.command()
def list():
    """List available trackers and mergers"""
    from . import list_mergers, list_trackers  # noqa: PLC0415

    # Create trackers table
    trackers_table = Table(title="Available Trackers")
    trackers_table.add_column("Name", style="cyan")
    trackers_table.add_column("Description", style="white")

    for tracker in list_trackers():
        desc = {
            "rfdetr": "Real-time object detection and tracking with RT-DETR",
            "dummy": "Test tracker that generates random tracks",
        }.get(tracker, "Custom tracker")
        trackers_table.add_row(tracker, desc)

    console.print(trackers_table)
    console.print()

    # Create mergers table
    mergers_table = Table(title="Available Mergers")
    mergers_table.add_column("Name", style="cyan")
    mergers_table.add_column("Description", style="white")

    for merger in list_mergers():
        desc = {"bev_cluster": "Bird's eye view clustering with ReID features"}.get(merger, "Custom merger")
        mergers_table.add_row(merger, desc)

    console.print(mergers_table)


@cli.command()
@click.argument("stream_urls", nargs=-1, required=True)
@click.option("--output", "-o", default="config.json", help="Output configuration file")
@click.option("--names", "-n", multiple=True, help="Camera names (same order as streams)")
def config(stream_urls, output, names):
    """Generate configuration file"""

    # Create config
    config_data = {
        "rtsp_streams": list(stream_urls),
        "camera_names": list(names) if names else [f"Camera {i}" for i in range(len(stream_urls))],
        "tracker_type": "rfdetr",
        "merger_type": "bev_cluster",
        "vision_fps": 10.0,
        "server_port": 8000,
        "server_name": "127.0.0.1",
    }

    # Write config
    with Path(output).open("w") as f:
        json.dump(config_data, f, indent=2)

    console.print(f"[green]✓[/green] Configuration saved to {output}")
    console.print("\nGenerated configuration:")
    console.print(json.dumps(config_data, indent=2))
    console.print(f"\nRun with: [cyan]trackstudio run --config {output}[/cyan]")


def main():
    """Main entry point for CLI"""
    cli()


if __name__ == "__main__":
    main()
