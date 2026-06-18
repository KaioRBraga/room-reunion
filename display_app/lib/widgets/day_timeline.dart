import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/display_status.dart';

class DayTimeline extends StatelessWidget {
  final List<MeetingSummary> events;
  final DateTime now;
  final int startHour;
  final int endHour;
  final double pixelsPerMinute;

  const DayTimeline({
    super.key,
    required this.events,
    required this.now,
    this.startHour = 7,
    this.endHour = 21,
    this.pixelsPerMinute = 1.4,
  });

  double _minutesFromStart(DateTime t) {
    final dayStart = DateTime(now.year, now.month, now.day, startHour);
    final minutes = t.difference(dayStart).inMinutes.toDouble();
    return minutes.clamp(0, (endHour - startHour) * 60).toDouble();
  }

  @override
  Widget build(BuildContext context) {
    final totalHeight = (endHour - startHour) * 60 * pixelsPerMinute;
    final timeFormat = DateFormat('HH:mm');
    final showNowLine = now.hour >= startHour && now.hour <= endHour;

    return SizedBox(
      width: double.infinity,
      height: totalHeight + 20,
      child: Stack(
        children: [
          for (var h = startHour; h <= endHour; h++)
            Positioned(
              top: (h - startHour) * 60 * pixelsPerMinute,
              left: 0,
              right: 0,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 40,
                    child: Text(
                      '${h.toString().padLeft(2, '0')}:00',
                      style: const TextStyle(color: Colors.white70, fontSize: 11),
                    ),
                  ),
                  const Expanded(child: Divider(height: 1, color: Colors.white24)),
                ],
              ),
            ),
          for (final event in events)
            Positioned(
              top: _minutesFromStart(event.start) * pixelsPerMinute + 14,
              left: 44,
              right: 0,
              height: ((event.end.difference(event.start).inMinutes) * pixelsPerMinute)
                  .clamp(16, totalHeight),
              child: Container(
                margin: const EdgeInsets.only(right: 4, bottom: 1),
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: event.isPast
                      ? Colors.white.withValues(alpha: 0.15)
                      : Colors.white.withValues(alpha: 0.32),
                  borderRadius: BorderRadius.circular(4),
                ),
                alignment: Alignment.topLeft,
                child: Text(
                  '${event.organizer}  ${event.title}',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
          if (showNowLine)
            Positioned(
              top: _minutesFromStart(now) * pixelsPerMinute + 14,
              left: 0,
              right: 0,
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                    color: Colors.white,
                    child: Text(
                      timeFormat.format(now),
                      style: const TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: Colors.black,
                      ),
                    ),
                  ),
                  const Expanded(
                    child: Divider(height: 1, color: Colors.white, thickness: 1.5),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
