import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/display_status.dart';
import 'day_timeline.dart';

class DisplayBody extends StatelessWidget {
  final DisplayStatus status;
  final bool busy;
  final VoidCallback? onCheckIn;
  final VoidCallback? onEnd;
  final VoidCallback? onExtend;
  final VoidCallback? onStartNow;
  final DateTime now;

  const DisplayBody({
    super.key,
    required this.status,
    required this.now,
    this.busy = false,
    this.onCheckIn,
    this.onEnd,
    this.onExtend,
    this.onStartNow,
  });

  static const _statusLabels = {
    DisplayStatusKind.startingSoon: 'Starting Soon',
    DisplayStatusKind.inUse: 'In Use',
    DisplayStatusKind.available: 'Available',
  };

  List<Color> get _gradientColors {
    switch (status.status) {
      case DisplayStatusKind.startingSoon:
        return [const Color(0xFFF2A65A), const Color(0xFFD9822B)];
      case DisplayStatusKind.inUse:
        return [const Color(0xFFE6645C), const Color(0xFFC0392B)];
      case DisplayStatusKind.available:
        return [const Color(0xFF57C16A), const Color(0xFF2E8B45)];
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: _gradientColors,
        ),
      ),
      child: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final isWide = constraints.maxWidth > constraints.maxHeight;
            final timeline = Padding(
              padding: const EdgeInsets.all(12),
              child: DayTimeline(events: status.todaySchedule, now: now),
            );

            if (isWide) {
              // Tablet/landscape: painel principal à esquerda, agenda do dia à direita.
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    flex: 6,
                    child: SingleChildScrollView(child: _mainContent(headlineSize: 48)),
                  ),
                  Container(width: 1, color: Colors.white24),
                  Expanded(
                    flex: 4,
                    child: SingleChildScrollView(child: timeline),
                  ),
                ],
              );
            }

            // Celular/retrato: tudo em coluna única, com scroll - garante que o
            // botão de ação nunca fique cortado fora da tela.
            return SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _mainContent(headlineSize: 36),
                  Container(height: 1, color: Colors.white24, margin: const EdgeInsets.symmetric(horizontal: 24)),
                  timeline,
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _mainContent({required double headlineSize}) {
    final meeting = status.currentMeeting ?? status.nextMeeting;

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          const Row(
            children: [
              Icon(Icons.meeting_room, color: Colors.white, size: 22),
              SizedBox(width: 8),
              Text(
                'ReadyRoom',
                style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Text(
            status.room.name,
            style: const TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: status.room.tags.map(_tagChip).toList(),
          ),
          const SizedBox(height: 28),
          Text(
            _statusLabels[status.status]!,
            key: const Key('statusHeadline'),
            style: TextStyle(color: Colors.white, fontSize: headlineSize, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 24),
          if (meeting != null) ..._meetingInfo(meeting),
          const SizedBox(height: 24),
          _actionButtons(),
        ],
      ),
    );
  }

  Widget _tagChip(String text) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          border: Border.all(color: Colors.white54),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(text, style: const TextStyle(color: Colors.white, fontSize: 12)),
      );

  List<Widget> _meetingInfo(MeetingSummary meeting) {
    final timeFormat = DateFormat('HH:mm');
    final rows = <Widget>[
      _infoRow(Icons.event_note, meeting.title),
      _infoRow(Icons.person, meeting.organizer),
    ];

    if (status.status == DisplayStatusKind.available) {
      final diff = meeting.start.difference(now);
      rows.add(_infoRow(Icons.schedule, 'Próxima reunião em ${_formatDuration(diff)}'));
    } else if (status.status == DisplayStatusKind.startingSoon && status.checkInDeadline != null) {
      final remaining = status.checkInDeadline!.difference(now);
      final text = remaining.isNegative ? '0:00' : _formatDuration(remaining);
      rows.add(
        _infoRow(
          Icons.schedule,
          '${timeFormat.format(meeting.start)} - ${timeFormat.format(meeting.end)}'
          '  ·  Check-in: $text',
        ),
      );
    } else {
      rows.add(
        _infoRow(Icons.schedule, '${timeFormat.format(meeting.start)} - ${timeFormat.format(meeting.end)}'),
      );
    }
    return rows;
  }

  Widget _infoRow(IconData icon, String text) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: Colors.white, size: 18),
            const SizedBox(width: 10),
            Expanded(
              child: Text(text, style: const TextStyle(color: Colors.white, fontSize: 16)),
            ),
          ],
        ),
      );

  String _formatDuration(Duration d) {
    final abs = d.isNegative ? -d : d;
    final hours = abs.inHours;
    final minutes = abs.inMinutes.remainder(60);
    if (hours > 0) return '${hours}h ${minutes}min';
    if (abs.inMinutes > 0) return '${abs.inMinutes}min ${abs.inSeconds.remainder(60)}s';
    return '${abs.inSeconds}s';
  }

  Widget _actionButtons() {
    switch (status.status) {
      case DisplayStatusKind.available:
        return _bigButton('Start Meeting Now', busy ? null : onStartNow);
      case DisplayStatusKind.startingSoon:
        if (status.currentMeeting?.checkedIn == true) {
          return _checkedInBadge();
        }
        return _bigButton('Check In', busy ? null : onCheckIn);
      case DisplayStatusKind.inUse:
        return Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            _bigButton('End', busy ? null : onEnd),
            _bigButton('Extend by 15 mins', busy ? null : onExtend, filled: false),
          ],
        );
    }
  }

  Widget _checkedInBadge() => Container(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        decoration: BoxDecoration(
          color: Colors.white24,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: Colors.white),
        ),
        child: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.check_circle, color: Colors.white, size: 20),
            SizedBox(width: 8),
            Text(
              'Check-in confirmado',
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
            ),
          ],
        ),
      );

  Widget _bigButton(String label, VoidCallback? onPressed, {bool filled = true}) {
    final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(999));
    final child = Text(label, style: const TextStyle(fontWeight: FontWeight.bold));

    if (filled) {
      return FilledButton(
        onPressed: onPressed,
        style: FilledButton.styleFrom(
          backgroundColor: Colors.white,
          foregroundColor: Colors.black87,
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 16),
          shape: shape,
        ),
        child: child,
      );
    }
    return OutlinedButton(
      onPressed: onPressed,
      style: OutlinedButton.styleFrom(
        foregroundColor: Colors.white,
        side: const BorderSide(color: Colors.white),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        shape: shape,
      ),
      child: child,
    );
  }
}
