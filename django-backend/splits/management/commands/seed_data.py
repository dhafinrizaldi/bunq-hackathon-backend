from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from splits.models import (
    OriginalTransaction,
    SplitSession,
    SplitParticipant,
    ReceiptItem,
    ItemAllocation,
    PaymentRequest,
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed fake split session data for development testing'

    def handle(self, *args, **options):
        self.stdout.write('Creating users...')

        admin, _ = User.objects.get_or_create(
            email='admin@example.com',
            defaults={'is_staff': True, 'is_superuser': True, 'username': 'admin'},
        )
        admin.set_password('admin')
        admin.save()

        jeremy, _ = User.objects.get_or_create(
            email='jeremy@example.com',
            defaults={'username': 'jeremy'},
        )
        jeremy.set_password('password')
        jeremy.save()

        ana, _ = User.objects.get_or_create(
            email='ana@example.com',
            defaults={'username': 'ana'},
        )
        ana.set_password('password')
        ana.save()

        tim, _ = User.objects.get_or_create(
            email='tim@example.com',
            defaults={'username': 'tim'},
        )
        tim.set_password('password')
        tim.save()

        self.stdout.write('Creating session 1: Bar Plein (partially paid)...')

        tx1, _ = OriginalTransaction.objects.get_or_create(
            bunq_transaction_id='bunq-tx-001',
            defaults={
                'initiator': admin,
                'merchant_name': 'Bar Plein',
                'total_amount': Decimal('45.50'),
                'currency': 'EUR',
                'date': timezone.now(),
            },
        )

        session1, created = SplitSession.objects.get_or_create(
            transaction=tx1,
            defaults={
                'user_prompt': (
                    'Jeremy and I shared the bitterballen and he had the Leffe, '
                    'I had the heineken, and Ana and Tim each had a fanta'
                ),
                'status': SplitSession.Status.COMPLETED,
                'ai_raw_response': {
                    'items': [
                        {'description': 'Leffe', 'price': 5.50, 'assigned_to': ['jeremy']},
                        {'description': 'Heineken', 'price': 4.50, 'assigned_to': ['admin']},
                        {'description': 'Bitterballen', 'price': 9.00, 'assigned_to': ['jeremy', 'admin']},
                        {'description': 'Fanta', 'price': 3.50, 'assigned_to': ['ana']},
                        {'description': 'Fanta', 'price': 3.50, 'assigned_to': ['tim']},
                    ]
                },
            },
        )

        if created:
            p_jeremy = SplitParticipant.objects.create(session=session1, user=jeremy)
            p_ana = SplitParticipant.objects.create(session=session1, user=ana)
            p_tim = SplitParticipant.objects.create(session=session1, user=tim)

            leffe = ReceiptItem.objects.create(session=session1, description='Leffe', total_price=Decimal('5.50'), quantity=1)
            heineken = ReceiptItem.objects.create(session=session1, description='Heineken', total_price=Decimal('4.50'), quantity=1)
            bitterballen = ReceiptItem.objects.create(session=session1, description='Bitterballen', total_price=Decimal('9.00'), quantity=1)
            fanta_ana = ReceiptItem.objects.create(session=session1, description='Fanta', total_price=Decimal('3.50'), quantity=1)
            fanta_tim = ReceiptItem.objects.create(session=session1, description='Fanta', total_price=Decimal('3.50'), quantity=1)

            ItemAllocation.objects.create(item=leffe, participant=p_jeremy, allocated_amount=Decimal('5.50'))
            ItemAllocation.objects.create(item=bitterballen, participant=p_jeremy, allocated_amount=Decimal('4.50'))
            ItemAllocation.objects.create(item=fanta_ana, participant=p_ana, allocated_amount=Decimal('3.50'))
            ItemAllocation.objects.create(item=fanta_tim, participant=p_tim, allocated_amount=Decimal('3.50'))

            PaymentRequest.objects.create(
                session=session1, payer=jeremy, payee=admin,
                amount=Decimal('10.00'), bunq_request_id='bunq-req-001', status=PaymentRequest.Status.PAID,
            )
            PaymentRequest.objects.create(
                session=session1, payer=ana, payee=admin,
                amount=Decimal('3.50'), bunq_request_id='bunq-req-002', status=PaymentRequest.Status.PENDING,
            )
            PaymentRequest.objects.create(
                session=session1, payer=tim, payee=admin,
                amount=Decimal('3.50'), bunq_request_id='bunq-req-003', status=PaymentRequest.Status.PENDING,
            )

        self.stdout.write('Creating session 2: Restaurant Blauw (fully paid)...')

        tx2, _ = OriginalTransaction.objects.get_or_create(
            bunq_transaction_id='bunq-tx-002',
            defaults={
                'initiator': admin,
                'merchant_name': 'Restaurant Blauw',
                'total_amount': Decimal('78.00'),
                'currency': 'EUR',
                'date': timezone.now(),
            },
        )

        session2, created = SplitSession.objects.get_or_create(
            transaction=tx2,
            defaults={
                'user_prompt': 'Split equally between all four of us',
                'status': SplitSession.Status.COMPLETED,
            },
        )

        if created:
            p2_jeremy = SplitParticipant.objects.create(session=session2, user=jeremy)
            p2_ana = SplitParticipant.objects.create(session=session2, user=ana)
            p2_tim = SplitParticipant.objects.create(session=session2, user=tim)

            PaymentRequest.objects.create(
                session=session2, payer=jeremy, payee=admin,
                amount=Decimal('19.50'), bunq_request_id='bunq-req-004', status=PaymentRequest.Status.PAID,
            )
            PaymentRequest.objects.create(
                session=session2, payer=ana, payee=admin,
                amount=Decimal('19.50'), bunq_request_id='bunq-req-005', status=PaymentRequest.Status.PAID,
            )
            PaymentRequest.objects.create(
                session=session2, payer=tim, payee=admin,
                amount=Decimal('19.50'), bunq_request_id='bunq-req-006', status=PaymentRequest.Status.PAID,
            )

        self.stdout.write(self.style.SUCCESS(
            '\nDone! Created 2 split sessions.\n'
            '  admin@example.com / admin\n'
            '  Session 1 (Bar Plein) — partially paid (Jeremy paid, Ana+Tim pending)\n'
            '  Session 2 (Restaurant Blauw) — fully paid\n'
        ))
