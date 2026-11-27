def plate_scale(tel: Telescope, cam: Camera, video_width: Optional[int] = None, as_video: bool = True) -> float:
    """Escala de placa en ″/px."""
    return 206.265 * cam.effective_pixel_um(video_width, as_video) / tel.focal_mm
