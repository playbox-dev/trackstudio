import argparse

import trackstudio as ts


def list_trackers():
    """List all available tracker examples."""
    print("📋 Available Custom Tracker Examples:")
    print()
    print("🤖 basic_example")
    print("   - Simple tracker template with essential structure")
    print("   - Minimal configuration and clear API documentation")
    print("   - Perfect starting point for custom tracker development")
    print()
    print("🚀 advanced_example")
    print("   - Comprehensive tracker template with advanced features")
    print("   - Multiple algorithm backends and configuration options")
    print("   - Performance monitoring and feature toggles")
    print("   - Production-ready template for complex scenarios")
    print()
    print("💡 Both examples focus on API structure and documentation")
    print("   rather than specific algorithms - perfect for learning!")
    print()


def main():
    """Main function to run tracker examples."""
    parser = argparse.ArgumentParser(description="TrackStudio Custom Tracker Examples")
    parser.add_argument("--tracker", choices=["basic", "advanced"], help="Which tracker example to run")
    parser.add_argument("--list", action="store_true", help="List available tracker examples")
    parser.add_argument(
        "--streams",
        nargs="+",
        default=["rtsp://localhost:8554/camera0", "rtsp://localhost:8554/camera1"],
        help="RTSP stream URLs",
    )
    parser.add_argument("--port", type=int, default=8000, help="Server port")

    args = parser.parse_args()

    if args.list:
        list_trackers()
        return

    if not args.tracker:
        print("❌ Please specify --tracker basic or --tracker advanced (or use --list to see options)")
        print("\n💡 Tip: These examples show the API structure with placeholder implementations.")
        print("   Add your own detection and tracking algorithms to make them functional!")
        return

    # Map tracker names to registered names
    tracker_map = {"basic": "basic_example", "advanced": "advanced_example"}

    tracker_name = tracker_map[args.tracker]

    print(f"🚀 Starting TrackStudio with {args.tracker} tracker example...")
    print(f"📹 Streams: {args.streams}")
    print(f"🌐 Port: {args.port}")
    print()
    print("⚠️  Note: This example uses placeholder algorithms and won't detect/track objects.")
    print("   Use it as a template to implement your own detection and tracking methods!")
    print()

    try:
        app = ts.launch(
            tracker=tracker_name,
            rtsp_streams=args.streams,
            camera_names=[f"Camera {i}" for i in range(len(args.streams))],
            server_port=args.port,
            open_browser=True,
        )

        print("✅ TrackStudio is running!")
        print(f"🎛️  Configure parameters: http://localhost:{args.port}")
        print("📊 Check the statistics panel to see your tracker's interface")
        print("🛑 Press Ctrl+C to stop")

        app.wait()

    except KeyboardInterrupt:
        print("\n🛑 Stopping TrackStudio...")
    except ImportError:
        print("❌ TrackStudio not installed. Run: pip install trackstudio")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
