import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/display_status.dart';
import '../theme/app_colors.dart';
import 'day_timeline.dart';

/// Tela principal do painel: agenda do dia em destaque (estilo calendário do
/// site, tema escuro). A ação principal de cada status (Iniciar agora / Fazer
/// check-in / Encerrar reunião) fica em destaque no topo, à direita, e o
/// status da sala é evidenciado numa faixa maior (cor + rótulo grande) junto
/// com a reunião atual/próxima, em vez de um badge pequeno.
class DisplayBody extends StatelessWidget {
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

  static const _statusLabels = {
    DisplayStatusKind.startingSoon: 'Começando',
    DisplayStatusKind.inUse: 'Em Uso',
    DisplayStatusKind.available: 'Disponível',
  };

  Color get _statusColor {
    switch (status.status) {
      case DisplayStatusKind.startingSoon:
        return status.layout.colorStartingSoon;
      case DisplayStatusKind.inUse:
        return status.layout.colorInUse;
      case DisplayStatusKind.available:
        return status.layout.colorAvailable;
    }
  }

  @override
  Widget build(BuildContext context) {
    final floatingButton = status.layout.buttonPosition == ButtonPosition.topRight;
    final agendaAbove = status.layout.agendaPosition == AgendaPosition.aboveStatus;
    final banner = _statusBanner(embedAction: !floatingButton);
    final agenda = _agendaArea();

    return Container(
      color: AppColors.bg,
      child: SafeArea(
        child: Stack(
          children: [
            Column(
              children: [
                _topBar(),
                if (agendaAbove) agenda else banner,
                if (agendaAbove) banner else agenda,
                _bottomBar(),
              ],
            ),
            if (floatingButton)
              Positioned(top: 16, right: 20, child: _primaryAction(compact: true)),
          ],
        ),
      ),
    );
  }

  Widget _agendaArea() {
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        child: Container(
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          clipBehavior: Clip.antiAlias,
          child: DayTimeline(events: status.todaySchedule, now: now, onSlotTap: onSlotTap),
        ),
      ),
    );
  }

  Widget _topBar() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
      decoration: const BoxDecoration(
        color: AppColors.ink,
        border: Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (status.layout.showLogo) ...[
            Center(child: _logoImage()),
            const SizedBox(height: 14),
          ],
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.end,
            spacing: 12,
            runSpacing: 8,
            children: [
              Text(
                status.room.name,
                style: const TextStyle(color: AppColors.text, fontSize: 24, fontWeight: FontWeight.w700),
              ),
              if (status.layout.showTags)
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: status.room.tags.map(_tagChip).toList(),
                ),
            ],
          ),
        ],
      ),
    );
  }

  /// Logo do app: usa a enviada pelo admin (`Layout do painel > Tablet`)
  /// quando configurada, com fallback pro asset padrão se a rede falhar -
  /// o tablet fica fixado na sala, então uma falha de rede não pode deixar
  /// a tela sem logo nenhuma.
  Widget _logoImage() {
    final url = status.layout.logoUrl;
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

  /// Ação principal do status. `compact` é usado quando o admin escolhe a
  /// posição "canto superior direito" (`ButtonPosition.topRight`) - o botão
  /// fica isolado sobre a barra de topo escura, então precisa ser menor pra
  /// não estourar a largura em telas estreitas (ver BUGS.md #2).
  Widget _primaryAction({bool compact = false}) {
    switch (status.status) {
      case DisplayStatusKind.available:
        final mainBtn = _bigActionButton(
          icon: Icons.play_arrow_rounded,
          label: 'Iniciar agora',
          onPressed: busy ? null : onStartNow,
          compact: compact,
        );
        return mainBtn;
      case DisplayStatusKind.startingSoon:
        if (status.currentMeeting?.checkedIn == true) {
          return _confirmedBadge();
        }
        return _bigActionButton(
          icon: Icons.login_rounded,
          label: 'Fazer check-in',
          onPressed: busy ? null : onCheckIn,
          compact: compact,
        );
      case DisplayStatusKind.inUse:
        return _bigActionButton(
          icon: Icons.stop_circle_outlined,
          label: 'Encerrar reunião',
          onPressed: busy ? null : onEnd,
          compact: compact,
        );
    }
  }

  /// Branco propositalmente - o botão fica em cima da faixa de status (que já
  /// é colorida) ou da barra de topo escura, então o contraste vem da cor do
  /// texto/ícone, não do fundo.
  Widget _bigActionButton({
    required IconData icon,
    required String label,
    required VoidCallback? onPressed,
    bool compact = false,
  }) {
    return FilledButton.icon(
      onPressed: onPressed,
      icon: Icon(icon, size: compact ? 22 : 32),
      label: Text(label, style: TextStyle(fontWeight: FontWeight.w700, fontSize: compact ? 15 : 21)),
      style: FilledButton.styleFrom(
        backgroundColor: Colors.white,
        foregroundColor: _statusColor,
        disabledBackgroundColor: Colors.white.withValues(alpha: 0.7),
        disabledForegroundColor: _statusColor.withValues(alpha: 0.6),
        padding: EdgeInsets.symmetric(horizontal: compact ? 18 : 40, vertical: compact ? 12 : 30),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(compact ? 12 : 16)),
      ),
    );
  }

  Widget _confirmedBadge() => Container(
        padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 20),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.check_circle, color: _statusColor, size: 26),
            const SizedBox(width: 10),
            Text(
              'Check-in confirmado',
              style: TextStyle(color: _statusColor, fontWeight: FontWeight.w700, fontSize: 16),
            ),
          ],
        ),
      );

  Widget _tagChip(String text) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: AppColors.surfaceAlt,
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(text, style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
      );

  IconData get _statusIcon {
    switch (status.status) {
      case DisplayStatusKind.startingSoon:
        return Icons.schedule;
      case DisplayStatusKind.inUse:
        return Icons.do_not_disturb_on_outlined;
      case DisplayStatusKind.available:
        return Icons.check_circle;
    }
  }

  /// Faixa de status: o fundo inteiro usa a cor do status (verde/âmbar/
  /// vermelho) pra ficar bem visível de longe, em vez de só um detalhe sutil.
  /// `embedAction` é false quando o botão foi configurado pra ficar isolado
  /// no canto superior direito (`ButtonPosition.topRight`) - nesse caso a
  /// faixa mostra só o texto de status, sem repetir o botão.
  Widget _statusBanner({required bool embedAction}) {
    final meeting = status.currentMeeting ?? status.nextMeeting;
    final textColumn = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          key: const Key('statusHeadline'),
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(_statusIcon, color: Colors.white, size: 22),
            const SizedBox(width: 10),
            Text(
              _statusLabels[status.status]!,
              style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w800),
            ),
          ],
        ),
        const SizedBox(height: 10),
        if (meeting != null) ..._meetingLines(meeting) else _emptyScheduleLine(),
      ],
    );
    final videoIcon = (meeting?.virtualRoomUrl != null && status.layout.showVideoIcon)
        ? const Padding(
            padding: EdgeInsets.only(right: 16),
            child: Icon(Icons.videocam_outlined, color: Colors.white, size: 20),
          )
        : null;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
      color: _statusColor,
      child: LayoutBuilder(
        builder: (context, constraints) {
          // Em telas estreitas (celular em retrato) o botão grande não cabe
          // ao lado do texto - empilha em vez de estourar a largura (overflow)
          // e usa a versão compacta do botão, senão ele domina a tela inteira
          // num celular (proporcional demais ao espaço disponível).
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
    );
  }

  Widget _emptyScheduleLine() => const Text(
        'Nenhuma reunião agendada para hoje.',
        style: TextStyle(color: Colors.white, fontSize: 13.5),
      );

  List<Widget> _meetingLines(MeetingSummary meeting) {
    final timeFormat = DateFormat('HH:mm');
    String timeInfo;
    if (status.status == DisplayStatusKind.available) {
      timeInfo = 'em ${_formatDuration(meeting.start.difference(now))} (${timeFormat.format(meeting.start)})';
    } else if (status.status == DisplayStatusKind.startingSoon && status.checkInDeadline != null) {
      final remaining = status.checkInDeadline!.difference(now);
      final text = remaining.isNegative ? '0:00' : _formatDuration(remaining);
      timeInfo = '${timeFormat.format(meeting.start)} - ${timeFormat.format(meeting.end)}  ·  Check-in: $text';
    } else {
      timeInfo = '${timeFormat.format(meeting.start)} - ${timeFormat.format(meeting.end)}';
    }

    final titlePrefix = status.status == DisplayStatusKind.available ? 'Próxima: ' : '';

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

  /// Conteúdo secundário no rodapé - some por completo quando não há nada a
  /// mostrar (ex: status "Começando" já com check-in feito).
  Widget _bottomBar() {
    final content = _secondaryContent();
    if (content == null) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 14, 20, 14),
      decoration: const BoxDecoration(
        color: AppColors.ink,
        border: Border(top: BorderSide(color: AppColors.border)),
      ),
      child: content,
    );
  }

  Widget? _secondaryContent() {
    switch (status.status) {
      case DisplayStatusKind.available:
        if (!status.layout.showScheduleHint) return null;
        return const Text(
          'Toque um horário livre na agenda para reservar com usuário e PIN',
          style: TextStyle(color: AppColors.textMuted, fontSize: 13),
        );
      case DisplayStatusKind.startingSoon:
        return null;
      case DisplayStatusKind.inUse:
        return Align(
          alignment: Alignment.centerLeft,
          child: _outlinedButton('Estender 15 min', busy ? null : onExtend),
        );
    }
  }

  Widget _outlinedButton(String label, VoidCallback? onPressed) {
    return OutlinedButton(
      onPressed: onPressed,
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.text,
        side: const BorderSide(color: AppColors.border),
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
      child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
    );
  }
}
