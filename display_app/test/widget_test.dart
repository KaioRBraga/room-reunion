import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:display_app/models/display_status.dart';
import 'package:display_app/widgets/display_body.dart';

DisplayStatus _buildStatus({
  required DisplayStatusKind status,
  MeetingSummary? currentMeeting,
  MeetingSummary? nextMeeting,
  DateTime? checkInDeadline,
}) {
  return DisplayStatus(
    room: RoomInfo(id: 1, name: 'Meeting Room 5', capacity: 10, equipmentNotes: 'Projector,TV'),
    status: status,
    currentMeeting: currentMeeting,
    nextMeeting: nextMeeting,
    checkInDeadline: checkInDeadline,
    todaySchedule: const [],
    serverTime: DateTime(2026, 6, 18, 10, 50),
  );
}

MeetingSummary _meeting({required DateTime start, required DateTime end, bool checkedIn = false}) {
  return MeetingSummary(
    id: 1,
    title: 'Demands Briefing',
    organizer: 'Carole',
    start: start,
    end: end,
    checkedIn: checkedIn,
    isPast: false,
  );
}

Widget _wrap(Widget child) => MaterialApp(home: Scaffold(body: child));

void main() {
  testWidgets('Available status: cor verde, texto Available e botão Start Meeting Now', (tester) async {
    final now = DateTime(2026, 6, 18, 10, 50);
    final status = _buildStatus(
      status: DisplayStatusKind.available,
      nextMeeting: _meeting(start: now.add(const Duration(hours: 2)), end: now.add(const Duration(hours: 3))),
    );

    await tester.pumpWidget(_wrap(DisplayBody(status: status, now: now)));

    expect(find.text('Available'), findsOneWidget);
    expect(find.text('Start Meeting Now'), findsOneWidget);
    expect(find.text('Check In'), findsNothing);

    final container = tester.widget<Container>(find.byType(Container).first);
    final gradient = (container.decoration as BoxDecoration).gradient as LinearGradient;
    expect(gradient.colors.first, const Color(0xFF57C16A));
  });

  testWidgets('Starting soon status: cor laranja, texto Starting Soon e botão Check In', (tester) async {
    final now = DateTime(2026, 6, 18, 10, 50);
    final start = now.add(const Duration(minutes: 10));
    final status = _buildStatus(
      status: DisplayStatusKind.startingSoon,
      currentMeeting: _meeting(start: start, end: start.add(const Duration(hours: 2))),
      checkInDeadline: start.add(const Duration(minutes: 5)),
    );

    await tester.pumpWidget(_wrap(DisplayBody(status: status, now: now)));

    expect(find.text('Starting Soon'), findsOneWidget);
    expect(find.text('Check In'), findsOneWidget);
    expect(find.textContaining('Check-in:'), findsOneWidget);

    final container = tester.widget<Container>(find.byType(Container).first);
    final gradient = (container.decoration as BoxDecoration).gradient as LinearGradient;
    expect(gradient.colors.first, const Color(0xFFF2A65A));
  });

  testWidgets('In use status: cor vermelha, texto In Use e botões End / Extend', (tester) async {
    final now = DateTime(2026, 6, 18, 9, 40);
    final start = now.subtract(const Duration(minutes: 40));
    final status = _buildStatus(
      status: DisplayStatusKind.inUse,
      currentMeeting: _meeting(start: start, end: start.add(const Duration(hours: 1)), checkedIn: true),
    );

    await tester.pumpWidget(_wrap(DisplayBody(status: status, now: now)));

    expect(find.text('In Use'), findsOneWidget);
    expect(find.text('End'), findsOneWidget);
    expect(find.text('Extend by 15 mins'), findsOneWidget);

    final container = tester.widget<Container>(find.byType(Container).first);
    final gradient = (container.decoration as BoxDecoration).gradient as LinearGradient;
    expect(gradient.colors.first, const Color(0xFFE6645C));
  });

  testWidgets('Botão Check In aciona o callback informado', (tester) async {
    final now = DateTime(2026, 6, 18, 10, 50);
    final start = now.add(const Duration(minutes: 2));
    final status = _buildStatus(
      status: DisplayStatusKind.startingSoon,
      currentMeeting: _meeting(start: start, end: start.add(const Duration(hours: 1))),
      checkInDeadline: start.add(const Duration(minutes: 5)),
    );

    var tapped = false;
    await tester.pumpWidget(
      _wrap(DisplayBody(status: status, now: now, onCheckIn: () => tapped = true)),
    );

    await tester.tap(find.text('Check In'));
    expect(tapped, isTrue);
  });

  testWidgets('Após check-in antes do início, mostra confirmação em vez do botão repetido', (tester) async {
    final now = DateTime(2026, 6, 18, 10, 50);
    final start = now.add(const Duration(minutes: 2));
    final status = _buildStatus(
      status: DisplayStatusKind.startingSoon,
      currentMeeting: _meeting(start: start, end: start.add(const Duration(hours: 1)), checkedIn: true),
      checkInDeadline: start.add(const Duration(minutes: 5)),
    );

    await tester.pumpWidget(_wrap(DisplayBody(status: status, now: now)));

    expect(find.text('Check-in confirmado'), findsOneWidget);
    expect(find.text('Check In'), findsNothing);
  });

  testWidgets('Em tela estreita (celular em retrato), o botão Check In continua visível e tocável', (tester) async {
    addTearDown(() => tester.view.resetPhysicalSize());
    tester.view.physicalSize = const Size(1080, 2340);
    tester.view.devicePixelRatio = 1.0;

    final now = DateTime(2026, 6, 18, 10, 50);
    final start = now.add(const Duration(minutes: 2));
    final status = _buildStatus(
      status: DisplayStatusKind.startingSoon,
      currentMeeting: _meeting(start: start, end: start.add(const Duration(hours: 1))),
      checkInDeadline: start.add(const Duration(minutes: 5)),
    );

    var tapped = false;
    await tester.pumpWidget(
      _wrap(DisplayBody(status: status, now: now, onCheckIn: () => tapped = true)),
    );

    expect(tester.takeException(), isNull);
    expect(find.text('Starting Soon'), findsOneWidget);

    final checkInFinder = find.text('Check In');
    expect(checkInFinder, findsOneWidget);
    await tester.ensureVisible(checkInFinder);
    await tester.tap(checkInFinder);
    expect(tapped, isTrue);
  });
}
