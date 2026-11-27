def effective_pixel_um(self, video_width: Optional[int] = None, as_video: bool = True) -> float:
    if self.video and as_video:
        w = video_width or (self.video_widths[0] if self.video_widths else self.width_px)
        return self.sensor_w_mm * 1000.0 / w
    return self.pixel_um
