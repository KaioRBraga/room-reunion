import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/display_status.dart';
import 'day_timeline.dart';

class DisplayBody extends StatefulWidget {
  final DisplayStatus status;
  final bool busy;
  final VoidCallback? onCheckIn;
  final VoidCallback? onEnd;
  final VoidCallback? onExtend;
  final VoidCallback? onStartNow;
  final void Function(DateTime start, DateTime end)? onSlotTap;
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
    this.onSlotTap,
  });

  @override
  State<DisplayBody> createState() => _DisplayBodyState();
}

class _DisplayBodyState extends State<DisplayBody> with TickerProviderStateMixin {
  static const _statusLabels = {
    DisplayStatusKind.startingSoon: 'Começando',
    DisplayStatusKind.inUse: 'Em Uso',
    DisplayStatusKind.available: 'Disponível',
  };

  late final AnimationController _entryCtrl;
  late final AnimationController _pulseCtrl;
  late final Animation<double> _topBarAnim;
  late final Animation<double> _bannerAnim;
  late final Animation<double> _agendaAnim;
  late final Animation<double> _pulseAnim;
  DisplayStatusKind? _lastStatus;

  @override
  void initState() {
    super.initState();
    _entryCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 700));
    _pulseCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 1800))
      ..repeat(reverse: true);
    _topBarAnim = CurvedAnimation(
      parent: _entryCtrl,
      curve: const Interval(0.0, 0.70, curve: Curves.easeOutCubic),
    );
    _bannerAnim = CurvedAnimation(
      parent: _entryCtrl,
      curve: const Interval(0.10, 0.85, curve: Curves.easeOutCubic),
    );
    _agendaAnim = CurvedAnimation(
      parent: _entryCtrl,
      curve: const Interval(0.05, 0.78, curve: Curves.easeOutCubic),
    );
    _pulseAnim = CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut);
    _lastStatus = widget.status.status;
    _entryCtrl.forward();
  }

  @override
  void didUpdateWidget(DisplayBody old) {
    super.didUpdateWidget(old);
    if (widget.status.status != _lastStatus) {
      _lastStatus = widget.status.status;
      _entryCtrl.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _entryCtrl.dispose();
    _pulseCtrl.dispose();
    super.dispose();
  }

  Color get _statusColor {
    switch (widget.status.status) {
      case DisplayStatusKind.startingSoon:
        return widget.status.layout.colorStartingSoon;
      case DisplayStatusKind.inUse:
        return widget.status.layout.colorInUse;
      case DisplayStatusKind.available:
        return widget.status.layout.colorAvailable;
    }
  }

  Widget _animated(Widget child, Animation<double> anim) {
    return AnimatedBuilder(
      animation: anim,
      child: child,
      builder: (_, ch) => Opacity(
        opacity: anim.value.clamp(0.0, 1.0),
        child: Transform.translate(
          offset: Offset(0, 14 * (1 - anim.value).clamp(0.0, 1.0)),
          child: ch,
        ),
      ),
    );
  }

  Widget _pulsingDot() {
    return AnimatedBuilder(
      animation: _pulseAnim,
      builder: (_, _) => Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(
          color: Colors.white,
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: Colors.white.withValues(alpha: 0.75 * _pulseAnim.value),
              blurRadius: 9 * _pulseAnim.value,
              spreadRadius: 2 * _pulseAnim.value,
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final floatingButton = widget.status.layout.buttonPosition == ButtonPosition.topRight;
    final agendaAbove = widget.status.layout.agendaPosition == AgendaPosition.aboveStatus;
    final banner = _animated(_statusBanner(embedAction: !floatingButton), _bannerAnim);
    final agenda = Expanded(child: _animated(_agendaContent(), _agendaAnim));

    return SafeArea(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(flex: 4, child: _leftPanel()),
          Expanded(
            flex: 6,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 500),
              color: _statusColor,
              child: Stack(
                children: [
                  Column(
                    children: [
                      if (agendaAbove) agenda else banner,
                      if (agendaAbove) banner else agenda,
                      _animated(_bottomBar(), _agendaAnim),
                    ],
                  ),
                  if (floatingButton)
                    Positioned(
                      top: 16,
                      right: 20,
                      child: _animated(_primaryAction(compact: true), _bannerAnim),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _leftPanel() {
    final meeting = widget.status.currentMeeting ?? widget.status.nextMeeting;
    return Stack(
      fit: StackFit.expand,
      children: [
        const ColoredBox(color: Color(0xFF0F172A)),
        const _NetworkBackground(),
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 28, 24, 28),
          child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (widget.status.layout.showLogo) ...[
            _animated(_logoImage(), _topBarAnim),
            const SizedBox(height: 28),
          ],
          _animated(
            Text(
              widget.status.room.name,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 24,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.5,
                height: 1.1,
              ),
            ),
            _topBarAnim,
          ),
          if (widget.status.layout.showTags) ...[
            const SizedBox(height: 10),
            _animated(
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: widget.status.room.tags.map(_tagChip).toList(),
              ),
              _topBarAnim,
            ),
          ],
          const Spacer(),
          _animated(_statusBadge(), _bannerAnim),
          if (meeting != null) ...[
            const SizedBox(height: 14),
            _animated(
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    meeting.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      height: 1.25,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    meeting.organizer,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.55),
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
              _bannerAnim,
            ),
          ],
        ],
      ),
    ),
  ],
);
  }

  Widget _statusBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: _statusColor.withValues(alpha: 0.18),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: _statusColor.withValues(alpha: 0.45)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _pulsingDot(),
          const SizedBox(width: 8),
          Text(
            _statusLabels[widget.status.status]!,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 13,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  Widget _agendaContent() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 6),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'AGENDA DE HOJE',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.08,
                ),
              ),
              Text(
                DateFormat('dd/MM/yyyy').format(widget.now),
                style: TextStyle(color: Colors.white.withValues(alpha: 0.55), fontSize: 12),
              ),
            ],
          ),
        ),
        Flexible(
          child: DayTimeline(
            events: widget.status.todaySchedule,
            now: widget.now,
            onSlotTap: widget.onSlotTap,
          ),
        ),
      ],
    );
  }

  Widget _logoImage() {
    final url = widget.status.layout.logoUrl;
    if (url == null) {
      return Image.asset('assets/img/logo-motivabpo.png', height: 48, fit: BoxFit.contain);
    }
    return Image.network(
      url,
      height: 48,
      fit: BoxFit.contain,
      errorBuilder: (context, error, stackTrace) =>
          Image.asset('assets/img/logo-motivabpo.png', height: 48, fit: BoxFit.contain),
    );
  }

  Widget _primaryAction({bool compact = false}) {
    switch (widget.status.status) {
      case DisplayStatusKind.available:
        return _bigActionButton(
          icon: Icons.play_arrow_rounded,
          label: 'Iniciar agora',
          onPressed: widget.busy ? null : widget.onStartNow,
          compact: compact,
        );
      case DisplayStatusKind.startingSoon:
        if (widget.status.currentMeeting?.checkedIn == true) {
          return _confirmedBadge();
        }
        return _bigActionButton(
          icon: Icons.login_rounded,
          label: 'Fazer check-in',
          onPressed: widget.busy ? null : widget.onCheckIn,
          compact: compact,
        );
      case DisplayStatusKind.inUse:
        return _bigActionButton(
          icon: Icons.stop_circle_outlined,
          label: 'Encerrar reunião',
          onPressed: widget.busy ? null : widget.onEnd,
          compact: compact,
        );
    }
  }

  Widget _bigActionButton({
    required IconData icon,
    required String label,
    required VoidCallback? onPressed,
    bool compact = false,
  }) {
    final enabled = onPressed != null;
    const dark = Color(0xFF0F172A);
    return Opacity(
      opacity: enabled ? 1.0 : 0.5,
      child: Material(
        color: Colors.white,
        borderRadius: BorderRadius.circular(999),
        clipBehavior: Clip.antiAlias,
        elevation: 0,
        child: InkWell(
          onTap: onPressed,
          splashColor: Colors.black.withValues(alpha: 0.08),
          highlightColor: Colors.black.withValues(alpha: 0.04),
          child: Padding(
            padding: EdgeInsets.symmetric(
              horizontal: compact ? 18 : 26,
              vertical: compact ? 12 : 14,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: compact ? 20 : 22, color: dark),
                SizedBox(width: compact ? 8 : 10),
                Text(
                  label,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 15,
                    color: dark,
                    letterSpacing: -0.3,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _confirmedBadge() => Container(
        padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 20),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF14532D), Color(0xFF1F9D55)],
          ),
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF1F9D55).withValues(alpha: 0.45),
              blurRadius: 18,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.check_circle, color: Colors.white, size: 26),
            SizedBox(width: 10),
            Text(
              'Check-in confirmado',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
                fontSize: 16,
              ),
            ),
          ],
        ),
      );

  Widget _tagChip(String text) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: Colors.white.withValues(alpha: 0.25)),
        ),
        child: Text(text, style: TextStyle(color: Colors.white.withValues(alpha: 0.75), fontSize: 11)),
      );

  Widget _statusBanner({required bool embedAction}) {
    final meeting = widget.status.currentMeeting ?? widget.status.nextMeeting;
    final textColumn = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          key: const Key('statusHeadline'),
          mainAxisSize: MainAxisSize.min,
          children: [
            _pulsingDot(),
            const SizedBox(width: 10),
            Text(
              _statusLabels[widget.status.status]!,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 20,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.3,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        if (meeting != null) ..._meetingLines(meeting) else _emptyScheduleLine(),
      ],
    );
    final videoIcon = (meeting?.virtualRoomUrl != null && widget.status.layout.showVideoIcon)
        ? const Padding(
            padding: EdgeInsets.only(right: 16),
            child: Icon(Icons.videocam_outlined, color: Colors.white, size: 20),
          )
        : null;

    return Container(
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.18),
        border: Border(bottom: BorderSide(color: Colors.white.withValues(alpha: 0.1))),
      ),
      child: Stack(
        children: [
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Colors.black.withValues(alpha: 0.1), Colors.transparent],
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
            child: LayoutBuilder(
              builder: (context, constraints) {
                if (constraints.maxWidth < 560) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      textColumn,
                      if (embedAction) ...[
                        const SizedBox(height: 16),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [?videoIcon, _primaryAction(compact: true)],
                        ),
                      ] else if (videoIcon != null) ...[
                        const SizedBox(height: 16),
                        Row(mainAxisAlignment: MainAxisAlignment.end, children: [videoIcon]),
                      ],
                    ],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Expanded(child: textColumn),
                    ?videoIcon,
                    if (embedAction) _primaryAction(),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _emptyScheduleLine() => const Text(
        'Nenhuma reunião agendada para hoje.',
        style: TextStyle(color: Colors.white, fontSize: 13.5),
      );

  List<Widget> _meetingLines(MeetingSummary meeting) {
    final timeFormat = DateFormat('HH:mm');
    String timeInfo;
    if (widget.status.status == DisplayStatusKind.available) {
      timeInfo =
          'em ${_formatDuration(meeting.start.difference(widget.now))} (${timeFormat.format(meeting.start)})';
    } else if (widget.status.status == DisplayStatusKind.startingSoon &&
        widget.status.checkInDeadline != null) {
      final remaining = widget.status.checkInDeadline!.difference(widget.now);
      final text = remaining.isNegative ? '0:00' : _formatDuration(remaining);
      timeInfo =
          '${timeFormat.format(meeting.start)} - ${timeFormat.format(meeting.end)}  ·  Check-in: $text';
    } else {
      timeInfo = '${timeFormat.format(meeting.start)} - ${timeFormat.format(meeting.end)}';
    }

    final titlePrefix = widget.status.status == DisplayStatusKind.available ? 'Próxima: ' : '';

    return [
      Text(
        '$titlePrefix${meeting.title}',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600),
      ),
      const SizedBox(height: 3),
      Text(
        '${meeting.organizer}  ·  $timeInfo',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(color: Colors.white70, fontSize: 13),
      ),
    ];
  }

  String _formatDuration(Duration d) {
    final abs = d.isNegative ? -d : d;
    final hours = abs.inHours;
    final minutes = abs.inMinutes.remainder(60);
    if (hours > 0) return '${hours}h ${minutes}min';
    if (abs.inMinutes > 0) return '${abs.inMinutes}min ${abs.inSeconds.remainder(60)}s';
    return '${abs.inSeconds}s';
  }

  Widget _bottomBar() {
    final content = _secondaryContent();
    if (content == null) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 14, 20, 14),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.18),
        border: Border(top: BorderSide(color: Colors.white.withValues(alpha: 0.1))),
      ),
      child: content,
    );
  }

  Widget? _secondaryContent() {
    switch (widget.status.status) {
      case DisplayStatusKind.available:
        if (!widget.status.layout.showScheduleHint) return null;
        return Text(
          'Toque um horário livre na agenda para reservar com usuário e PIN',
          style: TextStyle(color: Colors.white.withValues(alpha: 0.6), fontSize: 13),
        );
      case DisplayStatusKind.startingSoon:
        return null;
      case DisplayStatusKind.inUse:
        return Align(
          alignment: Alignment.centerLeft,
          child: _outlinedButton('Estender 15 min', widget.busy ? null : widget.onExtend),
        );
    }
  }

  Widget _outlinedButton(String label, VoidCallback? onPressed) {
    return OutlinedButton(
      onPressed: onPressed,
      style: OutlinedButton.styleFrom(
        foregroundColor: Colors.white,
        side: BorderSide(color: Colors.white.withValues(alpha: 0.4)),
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
      ),
      child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
    );
  }
}

// ─── Animação de rede do painel esquerdo ───────────────────────────────────

class _NetworkNode {
  double x, y, vx, vy;
  _NetworkNode({required this.x, required this.y, required this.vx, required this.vy});
}

class _NetworkBackground extends StatefulWidget {
  const _NetworkBackground();
  @override
  State<_NetworkBackground> createState() => _NetworkBackgroundState();
}

class _NetworkBackgroundState extends State<_NetworkBackground>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final List<_NetworkNode> _nodes;
  int _prevMs = 0;

  @override
  void initState() {
    super.initState();
    final rng = math.Random(7);
    _nodes = List.generate(16, (_) {
      final angle = rng.nextDouble() * 2 * math.pi;
      final speed = rng.nextDouble() * 0.035 + 0.008;
      return _NetworkNode(
        x: rng.nextDouble(),
        y: rng.nextDouble(),
        vx: math.cos(angle) * speed,
        vy: math.sin(angle) * speed,
      );
    });
    _ctrl = AnimationController(vsync: this, duration: const Duration(seconds: 1))
      ..repeat()
      ..addListener(_tick);
  }

  void _tick() {
    final now = DateTime.now().millisecondsSinceEpoch;
    if (_prevMs == 0) { _prevMs = now; return; }
    final dt = (now - _prevMs).clamp(0, 100) / 1000.0;
    _prevMs = now;
    for (final n in _nodes) {
      n.x = (n.x + n.vx * dt + 1.0) % 1.0;
      n.y = (n.y + n.vy * dt + 1.0) % 1.0;
    }
    setState(() {});
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: _NetworkPainter(_nodes), size: Size.infinite);
  }
}

class _NetworkPainter extends CustomPainter {
  final List<_NetworkNode> nodes;
  _NetworkPainter(this.nodes);

  static const _maxDist = 0.30;

  @override
  void paint(Canvas canvas, Size size) {
    final linePaint = Paint()..strokeWidth = 0.9;
    for (int i = 0; i < nodes.length; i++) {
      for (int j = i + 1; j < nodes.length; j++) {
        final ni = nodes[i], nj = nodes[j];
        final dx = ni.x - nj.x;
        final dy = ni.y - nj.y;
        final d = math.sqrt(dx * dx + dy * dy);
        if (d < _maxDist) {
          linePaint.color = Color.fromRGBO(255, 255, 255, (1.0 - d / _maxDist) * 0.18);
          canvas.drawLine(
            Offset(ni.x * size.width, ni.y * size.height),
            Offset(nj.x * size.width, nj.y * size.height),
            linePaint,
          );
        }
      }
    }
    final dotPaint = Paint()..color = const Color.fromRGBO(255, 255, 255, 0.38);
    for (final n in nodes) {
      canvas.drawCircle(Offset(n.x * size.width, n.y * size.height), 2.5, dotPaint);
    }
  }

  @override
  bool shouldRepaint(_NetworkPainter _) => true;
}
