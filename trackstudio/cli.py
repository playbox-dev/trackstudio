"""
TrackStudio CLI - Command-line interface for TrackStudio
"""

import json
import sys
import logging # Import logging
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
    type=str,
    help="Vision tracker to use (rfdetr, dummy, or custom)",
)
@click.option("--merger", "-m", default="bev_cluster", help="Cross-camera merger to use")
@click.option("--port", "-p", default=8000, type=int, help="Server port")
@click.option("--host", "-h", default="127.0.0.1", help="Server host")
@click.option("--share", is_flag=True, help="Create public URL")
@click.option("--no-browser", is_flag=True, help="Do not open browser automatically")
@click.option("--vision-fps", default=10.0, type=float, help="Vision processing FPS")
# MODIFIED: Allow multiple calibration files, format ID=PATH
@click.option(
    "--calibration-files", 
    "-cf", # Added short option for convenience
    multiple=True, 
    type=str, 
    metavar="ID=PATH",
    help="Calibration data files (e.g., -cf 0=cam0.json -cf 1=cam1.json). IDs must match stream order in config or --streams."
)
# NEW: Option to enable undistortion
@click.option(
    "--enable-undistortion",
    "-eu", # Added short option
    is_flag=True,
    help="Enable camera undistortion based on calibration data."
)
@click.option("--debug", is_flag=True, help="Enable debug logging")
def run(
    streams, config, tracker, merger, port, host, share, no_browser,
    vision_fps, calibration_files, enable_undistortion, debug
):
    """Run TrackStudio server"""

    app_logger = logging.getLogger(__name__) # Get logger for this module

    # Show banner
    console.print(
        Panel.fit("[bold blue]TrackStudio[/bold blue] 🎥\nMulti-Camera Vision Tracking System", border_style="blue")
    )

    # Load config file if provided
    config_data = {}
    if config:
        try:
            with Path(config).open() as f:
                config_data = json.load(f)
            console.print(f"[green]✓[/green] Loaded config from {config}")
        except FileNotFoundError:
            console.print(f"[red]Error:[/red] Config file not found at {config}")
            app_logger.error(f"Config file not found: {config}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error:[/red] Invalid JSON in config file {config}: {e}")
            app_logger.error(f"Invalid JSON in config file {config}: {e}")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to load config file {config}: {e}")
            app_logger.error(f"Failed to load config file {config}: {e}")
            sys.exit(1)


    # Use streams from command line or config
    # Command line --streams take precedence over config_data.rtsp_streams
    if streams:
        config_data["rtsp_streams"] = list(streams)
    elif "rtsp_streams" not in config_data or not config_data["rtsp_streams"]:
        # Fallback to defaults if neither CLI nor config provides streams
        config_data["rtsp_streams"] = ["rtsp://localhost:8554/camera0", "rtsp://localhost:8554/camera1"]
        app_logger.info("No RTSP streams specified, using defaults.")

    # Process camera names (can be from config or automatically generated)
    if "camera_names" not in config_data or not config_data["camera_names"]:
        num_streams_defined = len(config_data.get("rtsp_streams", []))
        config_data["camera_names"] = [f"Camera {i}" for i in range(num_streams_defined)]
        app_logger.info(f"No camera names specified, generating {num_streams_defined} default names.")


    # --- NEW: Handle calibration files and undistortion setting ---
    # Prepare calibration file paths dictionary
    cli_calibration_paths = {}
    if calibration_files:
        for item in calibration_files:
            try:
                stream_id_str, file_path = item.split('=', 1)
                stream_id = int(stream_id_str)
                cli_calibration_paths[stream_id] = file_path
            except ValueError:
                console.print(f"[red]Error:[/red] Invalid format for --calibration-files: '{item}'. Expected 'ID=PATH'.")
                app_logger.error(f"Invalid format for --calibration-files: '{item}'. Expected 'ID=PATH'.")
                sys.exit(1)
    
    # Merge CLI calibration paths with any from config_data, with CLI taking precedence
    if "calibration_files" not in config_data:
        config_data["calibration_files"] = {}
    
    # Ensure config_data["calibration_files"] is a dictionary and contains integer keys
    if isinstance(config_data["calibration_files"], dict):
        # Convert keys from string to int if they are strings (typical for JSON)
        config_data["calibration_files"] = {
            int(k): v for k, v in config_data["calibration_files"].items()
        }
    else:
        app_logger.warning("Config file's 'calibration_files' is not a dictionary, ignoring it.")
        config_data["calibration_files"] = {} # Reset to empty dict if malformed

    config_data["calibration_files"].update(cli_calibration_paths)
    
    # Set enable_undistortion flag. CLI argument takes precedence.
    if enable_undistortion:
        config_data["enable_undistortion"] = True
    elif "enable_undistortion" not in config_data:
        config_data["enable_undistortion"] = False # Default to False if not in config or CLI

    # --- End NEW: Handle calibration files and undistortion setting ---


    # Import here to avoid circular imports and ensure ServerConfig is fully loaded
    from . import launch 
    from .core.config import ServerConfig # Import ServerConfig here

    # Populate ServerConfig with the resolved values
    ServerConfig.VISION_API_ENABLED = config_data.get("vision_api_enabled", ServerConfig.VISION_API_ENABLED)
    ServerConfig.ENABLE_UNDISTORTION = config_data.get("enable_undistortion", False) # Ensure default is False
    ServerConfig.CALIBRATION_FILES = config_data["calibration_files"] # Set the populated dict
    
    # Also ensure streams and names are set for ServerConfig.get_enabled_streams()
    ServerConfig._config_data["rtsp_streams"] = config_data["rtsp_streams"]
    ServerConfig._config_data["camera_names"] = config_data["camera_names"]


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
    table.add_row("Enable Undistortion", "Yes" if ServerConfig.ENABLE_UNDISTORTION else "No") # Display new setting
    
    # Display calibration files if any
    if ServerConfig.CALIBRATION_FILES:
        cal_files_str = "\n".join([f"  {k}: {v}" for k, v in ServerConfig.CALIBRATION_FILES.items()])
        table.add_row("Calibration Files", cal_files_str)
    else:
        table.add_row("Calibration Files", "None specified")

    console.print(table)
    console.print()

    # List streams
    console.print("[bold]Stream URLs:[/bold]")
    for i, stream in enumerate(config_data.get("rtsp_streams", [])):
        console.print(f"  {i + 1}. {stream}")
    console.print()

    try:
        # Launch TrackStudio. The 'launch' function should then read from ServerConfig.
        # No need to pass calibration_file or rtsp_streams directly here anymore,
        # as ServerConfig should hold the definitive truth.
        app = launch(
            tracker=config_data.get("tracker", tracker),
            merger=config_data.get("merger", merger),
            vision_fps=config_data.get("vision_fps", vision_fps),
            server_name=config_data.get("server_name", host),
            server_port=config_data.get("server_port", port),
            share=config_data.get("share", share),
            open_browser=config_data.get("open_browser", not no_browser),
            # calibration_file=config_data.get("calibration_file", calibration_file), # REMOVED
            # rtsp_streams=config_data.get("rtsp_streams", streams), # REMOVED
            # The launch function should implicitly use ServerConfig now
        )

        # Keep running until interrupted
        app.wait()

    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
def demo():
    """Run TrackStudio with demo configuration"""
    from . import demo as run_demo

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
    from . import list_mergers, list_trackers

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
@click.option(
    "--calibration-files", 
    "-cf", 
    multiple=True, 
    type=str, 
    metavar="ID=PATH",
    help="Calibration data files to include in the config (e.g., -cf 0=cam0.json -cf 1=cam1.json)."
)
@click.option(
    "--enable-undistortion",
    "-eu", 
    is_flag=True,
    help="Include enable_undistortion flag in the config file."
)
def config(stream_urls, output, names, calibration_files, enable_undistortion):
    """Generate configuration file"""

    # Process CLI calibration files for config generation
    config_cal_files = {}
    if calibration_files:
        for item in calibration_files:
            try:
                stream_id_str, file_path = item.split('=', 1)
                stream_id = int(stream_id_str)
                config_cal_files[str(stream_id)] = file_path # Store as string keys for JSON
            except ValueError:
                console.print(f"[red]Error:[/red] Invalid format for --calibration-files: '{item}'. Expected 'ID=PATH'.")
                sys.exit(1)

    # Create config data
    config_data = {
        "rtsp_streams": list(stream_urls),
        "camera_names": list(names) if names else [f"Camera {i}" for i in range(len(stream_urls))],
        "tracker_type": "rfdetr",
        "merger_type": "bev_cluster",
        "vision_fps": 10.0,
        "server_port": 8000,
        "server_name": "127.0.0.1",
        "calibration_files": config_cal_files, # Add calibration files to config
        "enable_undistortion": enable_undistortion # Add enable_undistortion to config
    }

    # Write config
    try:
        with Path(output).open("w") as f:
            json.dump(config_data, f, indent=2)
        console.print(f"[green]✓[/green] Configuration saved to {output}")
        console.print("\nGenerated configuration:")
        console.print(json.dumps(config_data, indent=2))
        console.print(f"\nRun with: [cyan]trackstudio run --config {output}[/cyan]")
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to write config file {output}: {e}")
        sys.exit(1)


def main():
    """Main entry point for CLI"""
    cli()


if __name__ == "__main__":
    main()