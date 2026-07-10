#!/usr/bin/env bash
# Clean (remove) container image
# Usage: clean.sh [version] [REPO]

set -e

VERSION="${1:-dev}"
# Handle case where just passes "version=X" instead of just "X"
if [[ "$VERSION" =~ ^version= ]]; then
	VERSION="${VERSION#version=}"
fi

REPO="${2:-${TEST_REGISTRY:-ghcr.io/vig-os/devkit}}"
# Strip trailing slash if present
REPO="${REPO%/}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

IMAGE_NAME="$REPO:$VERSION"

# Remove manifest list first (if it exists)
# When pulling multi-arch manifests, podman creates local manifest lists
if podman manifest exists "$IMAGE_NAME" 2>/dev/null; then
	echo "Removing manifest list $IMAGE_NAME..."
	if ! podman manifest rm "$IMAGE_NAME" 2>/dev/null; then
		echo "⚠️  Failed to remove manifest list $IMAGE_NAME"
		exit 1
	fi
	echo "✓ Removed manifest list $IMAGE_NAME"
fi

# Get list of actual local images (not just resolvable through registry)
# Handle errors gracefully (e.g., corrupted images)
LOCAL_IMAGES=$(podman images --format "{{.Repository}}:{{.Tag}}" 2>/dev/null || echo "")

# Remove arch-specific tags FIRST (e.g., -amd64, -arm64)
# These are created when pulling multi-arch manifests
# Removing them first ensures the arch-less tag can be properly removed
for arch in amd64 arm64; do
	ARCH_TAG="${IMAGE_NAME}-${arch}"
	if echo "$LOCAL_IMAGES" | grep -q "^${ARCH_TAG}$"; then
		echo "Removing arch-specific image $ARCH_TAG..."
		if ! podman rmi -f "$ARCH_TAG" 2>/dev/null; then
			echo "⚠️  Failed to remove $ARCH_TAG"
			exit 1
		fi
		echo "✓ Removed image $ARCH_TAG"
	fi
done

# Remove arch-less tag if it exists locally
if echo "$LOCAL_IMAGES" | grep -q "^${IMAGE_NAME}$"; then
	echo "Removing image $IMAGE_NAME..."
	# Try removing as manifest first
	podman manifest rm "$IMAGE_NAME" 2>/dev/null || true
	# Then try removing as image
	if ! podman rmi -f "$IMAGE_NAME" 2>/dev/null; then
		echo "⚠️  Failed to remove $IMAGE_NAME"
		exit 1
	fi
	echo "✓ Removed image $IMAGE_NAME"
fi

# Final verification: check if anything matching this tag still exists
if podman image exists "$IMAGE_NAME" 2>/dev/null; then
	echo "⚠️  Warning: $IMAGE_NAME still exists after cleanup attempt"
	# Try one more time with force removal
	podman manifest rm "$IMAGE_NAME" 2>/dev/null || true
	podman rmi -f "$IMAGE_NAME" 2>/dev/null || true
	# If it still exists, that's a problem but we'll let it fail naturally
	if podman image exists "$IMAGE_NAME" 2>/dev/null; then
		echo "❌ Error: $IMAGE_NAME could not be removed"
		exit 1
	fi
fi
