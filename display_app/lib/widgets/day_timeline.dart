import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/display_status.dart';
import '../theme/app_colors.dart';

class DayTimeline extends StatefulWidget {
  final List<MeetingSummary> events;
  final DateTime now;
  final int startHour;
  final int endHour;
  final double pixelsPerMinute;
  final void Function(DateTime start, DateTime end)? onSlotTap;

  const DayTimeline({
    super.key,
    required this.events,
    required this.now,
    this.startHour = 7,
    this.endHour = 21,
    this.pixelsPerMinute = 1.8,
    this.onSlotTap,
  });

  @override
  State<DayTimeline> createState() => _DayTimelineState();
}

class _DayTimelineState extends State<DayTimeline> {
  DateTime? _pressedSlotStart;

  double _minutesFromStart(DateTime t) {
    final dayStart = DateTime(widget.now.year, widget.now.month, widget.now.day, widget.startHour);
    final minutes = t.difference(dayStart).inMinutes.toDouble();
    return minutes.clamp(0, (widget.endHour - widget.startHour) * 60).toDouble();
  }

  bool _isSlotFree(DateTime start, DateTime end) {
    return !widget.events.any((e) => e.start.isBefore(end) && e.end.isAfter(start));
  }

  DateTime _slotStartFromLocalY(double localY) {
    final dayStart = DateTime(widget.now.year, widget.now.month, widget.now.day, widget.startHour);
    final tappedMinutes =
        (localY / widget.pixelsPerMinute).clamp(0, (widget.endHour - widget.startHour) * 60).toDouble();
    final roundedMinutes = (tappedMinutes / 30).round() * 30;
    var slotStart = dayStart.add(Duration(minutes: roundedMinutes));

    if (slotStart.isBefore(widget.now)) {
      final nowMinutes = widget.now.difference(dayStart).inMinutes;
      final nextSlotMinutes = (nowMinutes / 30).ceil() * 30;
      slotStart = dayStart.add(Duration(minutes: nextSlotMinutes));
    }
    return slotStart;
  }

  void _handleTapDown(Offset localPosition) {
    if (widget.onSlotTap == null) return;
    setState(() => _pressedSlotStart = _slotStartFromLocalY(localPosition.dy));
  }

  void _handleTapCancel() {
    if (_pressedSlotStart != null) setState(() => _pressedSlotStart = null);
  }

  void _handleTap(BuildContext context, Offset localPosition) {
    final slotStart = _slotStartFromLocalY(localPosition.dy);
    final slotEnd = slotStart.add(const Duration(minutes: 30));
    setState(() => _pressedSlotStart = null);

    if (!_isSlotFree(slotStart, slotEnd)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Horário ocupado - escolha outro.')),
      );
      return;
    }
    widget.onSlotTap!(slotStart, slotEnd);
  }

  @override
  Widget build(BuildContext context) {
    final totalHeight = (widget.endHour - widget.startHour) * 60 * widget.pixelsPerMinute;
    final timeFormat = DateFormat('HH:mm');
    final showNowLine = widget.now.hour >= widget.startHour && widget.now.hour <= widget.endHour;
    final pressedStart = _pressedSlotStart;

    final stack = SizedBox(
      width: double.infinity,
      height: totalHeight + 20,
      child: Stack(
        children: [
          for (var h = widget.startHour; h <= widget.endHour; h++)
            Positioned(
              top: (h - widget.startHour) * 60 * widget.pixelsPerMinute,
              left: 0,
              right: 0,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 52,
                    child: Padding(
                      padding: const EdgeInsets.only(left: 14),
                      child: Text(
                        '${h.toString().padLeft(2, '0')}:00',
                        style: const TextStyle(color: AppColors.textMuted, fontSize: 12),
                      ),
                    ),
                  ),
                  const Expanded(child: Divider(height: 1, color: AppColors.border)),
                  const SizedBox(width: 14),
                ],
              ),
            ),
          if (pressedStart != null)
            Positioned(
              top: _minutesFromStart(pressedStart) * widget.pixelsPerMinute + 14,
              left: 52,
              right: 14,
              height: 30 * widget.pixelsPerMinute,
              child: Container(
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.22),
                  border: Border.all(color: AppColors.primary, width: 1.5),
                  borderRadius: BorderRadius.circular(6),
                ),
              ),
            ),
          for (final event in widget.events)
            Positioned(
              top: _minutesFromStart(event.start) * widget.pixelsPerMinute + 14,
              left: 52,
              right: 14,
              height: ((event.end.difference(event.start).inMinutes) * widget.pixelsPerMinute)
                  .clamp(18, totalHeight),
              child: Container(
                margin: const EdgeInsets.only(bottom: 2),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: event.isPast
                      ? AppColors.surfaceAlt
                      : AppColors.primary.withValues(alpha: 0.85),
                  borderRadius: BorderRadius.circular(6),
                  border: Border(
                    left: BorderSide(
                      color: event.isPast ? AppColors.border : AppColors.primaryDark,
                      width: 3,
                    ),
                  ),
                ),
                alignment: Alignment.topLeft,
                child: Text(
                  '${event.organizer} · ${event.title}',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: event.isPast ? AppColors.textMuted : Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
          if (showNowLine)
            Positioned(
              top: _minutesFromStart(widget.now) * widget.pixelsPerMinute + 14,
              left: 0,
              right: 0,
              child: Row(
                children: [
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppColors.primary,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      timeFormat.format(widget.now),
                      style: const TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                  ),
                  const Expanded(
                    child: Divider(height: 1, color: AppColors.primary, thickness: 1.5),
                  ),
                  const SizedBox(width: 14),
                ],
              ),
            ),
        ],
      ),
    );

    if (widget.onSlotTap == null) {
      return SingleChildScrollView(padding: const EdgeInsets.symmetric(vertical: 8), child: stack);
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTapDown: (details) => _handleTapDown(details.localPosition),
        onTapCancel: _handleTapCancel,
        onTapUp: (details) => _handleTap(context, details.localPosition),
        child: stack,
      ),
    );
  }
}
